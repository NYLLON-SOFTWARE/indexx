"""Release resolution through fixture GitHub responses; never use live credentials."""
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock
from urllib.parse import parse_qs, urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("indexx_update", REPO_ROOT / "scripts/indexx_update.py")
updater = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(updater)
MAIN = "a" * 40
OLD = "b" * 40
ADVANCED = "c" * 40
WORKFLOW_ID = 17


def run_record(run_id=101, number=10, attempt=1, commit=MAIN, **changes):
    result = {"id": run_id, "run_number": number, "run_attempt": attempt, "head_sha": commit,
              "head_branch": "main", "event": "push", "workflow_id": WORKFLOW_ID,
              "path": ".github/workflows/validate.yml", "repository": {"full_name": "kropdx/indexx"},
              "head_repository": {"full_name": "kropdx/indexx"}, "status": "completed", "conclusion": "success"}
    result.update(changes)
    return result


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.ref_calls = 0
        self.runs = [run_record()]
        self.details = {101: run_record()}
        self.workflow = {"id": WORKFLOW_ID, "path": updater.WORKFLOW}
        self.comparison = {"status": "ahead", "base_commit": {"sha": OLD}, "merge_base_commit": {"sha": OLD}}
        self.main = MAIN
        self.after_first_ref = ADVANCED
        self.error_at = None
        self.mock_process = mock.patch.object(updater.subprocess, "run", side_effect=self.gh)
        self.process = self.mock_process.start()
        self.addCleanup(self.mock_process.stop)

    def gh(self, command, **options):
        # Assert that the implementation cannot silently use shell interpolation,
        # another repository/host, writes, or caller-managed authentication.
        self.assertEqual(command[:6], ["gh", "api", "--hostname", "github.com", "--method", "GET"])
        self.assertNotIn("shell", options)
        self.assertEqual(options["timeout"], 30)
        endpoint = command[-1]
        self.assertTrue(endpoint.startswith("repos/kropdx/indexx/"))
        self.calls.append(endpoint)
        if self.error_at is not None and self.error_at in endpoint:
            return subprocess.CompletedProcess(command, 1, stdout="", stderr="private authentication detail must not be echoed")
        if endpoint.endswith("/git/ref/heads/main"):
            self.ref_calls += 1
            payload = {"ref": "refs/heads/main", "object": {"type": "commit", "sha": self.main if self.ref_calls == 1 else self.after_first_ref}}
        elif "/compare/" in endpoint:
            self.assertEqual(endpoint, f"repos/kropdx/indexx/compare/{OLD}...{self.main}")
            payload = self.comparison
        elif endpoint.endswith("/actions/workflows/validate.yml"):
            payload = self.workflow
        elif "/actions/workflows/" in endpoint and "/runs?" in endpoint:
            query = parse_qs(urlparse(endpoint).query)
            self.assertEqual(query["branch"], ["main"])
            self.assertEqual(query["event"], ["push"])
            self.assertNotIn("status", query)
            self.assertEqual(query["per_page"], ["100"])
            page = int(query["page"][0])
            payload = {"total_count": len(self.runs), "workflow_runs": self.runs[(page - 1) * 100:page * 100]}
        elif "/actions/runs/" in endpoint:
            payload = self.details[int(endpoint.rsplit("/", 1)[1])]
        else:
            self.fail("Unexpected API endpoint: " + endpoint)
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    def test_main_is_resolved_once_and_later_advancement_cannot_change_selection(self):
        result = updater.resolve_release()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["commit"], MAIN)
        self.assertEqual(result["main_commit"], MAIN)
        self.assertEqual(self.ref_calls, 1)
        self.assertNotIn(ADVANCED, " ".join(self.calls))
        query_call = next(call for call in self.calls if "/runs?" in call)
        self.assertEqual(parse_qs(urlparse(query_call).query)["head_sha"], [MAIN])
        self.assertEqual(result["ci"], {"workflow": updater.WORKFLOW, "workflow_id": WORKFLOW_ID,
                                      "run_id": 101, "run_number": 10, "run_attempt": 1, "event": "push",
                                      "branch": "main", "commit": MAIN, "status": "completed", "conclusion": "success",
                                      "url": "https://github.com/kropdx/indexx/actions/runs/101/attempts/1"})

    def test_invalid_revision_is_blocked_before_any_api_request(self):
        for revision in ("abc123", "g" * 40, "main", MAIN + "\n", "../main", 123):
            with self.subTest(revision=revision):
                result = updater.resolve_release(revision)
                self.assertEqual(result["status"], "blocked")
                self.assertIn("full 40-character", result["reason"])
                self.assertEqual(self.calls, [])

    def test_historical_revision_requires_ancestry_and_its_own_exact_sha_ci(self):
        self.runs = [run_record(commit=OLD)]
        self.details[101] = run_record(commit=OLD)
        result = updater.resolve_release(OLD.upper())
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["commit"], OLD)
        self.assertEqual(result["main_commit"], MAIN)
        self.assertIn(f"repos/kropdx/indexx/compare/{OLD}...{MAIN}", self.calls)
        self.assertEqual(self.ref_calls, 1)
        query_call = next(call for call in self.calls if "/runs?" in call)
        self.assertEqual(parse_qs(urlparse(query_call).query)["head_sha"], [OLD])

    def test_unreachable_or_mismatched_comparison_never_queries_ci(self):
        for comparison in (
            {"status": "behind", "base_commit": {"sha": OLD}, "merge_base_commit": {"sha": OLD}},
            {"status": "diverged", "base_commit": {"sha": OLD}, "merge_base_commit": {"sha": ADVANCED}},
            {"status": "ahead", "base_commit": {"sha": MAIN}, "merge_base_commit": {"sha": OLD}},
            {"status": "ahead", "base_commit": {"sha": OLD}, "merge_base_commit": {"sha": MAIN}},
        ):
            with self.subTest(comparison=comparison):
                self.ref_calls = 0
                self.calls.clear()
                self.comparison = comparison
                result = updater.resolve_release(OLD)
                self.assertEqual(result["status"], "blocked")
                self.assertIn("reachable", result["reason"])
                self.assertFalse(any("/actions/" in call for call in self.calls))

    def test_explicit_current_main_pin_does_not_need_a_comparison(self):
        self.assertEqual(updater.resolve_release(MAIN)["status"], "ready")
        self.assertFalse(any("/compare/" in call for call in self.calls))

    def test_wrong_event_branch_sha_workflow_or_repository_is_not_evidence(self):
        for changes in ({"event": "pull_request"}, {"event": "workflow_dispatch"}, {"head_branch": "feature"},
                        {"head_sha": OLD}, {"workflow_id": 99}, {"path": ".github/workflows/other.yml"},
                        {"repository": {"full_name": "other/indexx"}}, {"head_repository": {"full_name": "other/indexx"}},
                        {"repository": {"full_name": None}}):
            with self.subTest(changes=changes):
                self.ref_calls = 0
                self.runs = [run_record(**changes)]
                result = updater.resolve_release()
                self.assertEqual(result["status"], "blocked")
                self.assertIn("No validation push run", result["reason"])

    def test_eligible_runs_are_filtered_before_ordering(self):
        self.runs += [run_record(run_id=999, number=99, event="pull_request")]
        self.assertEqual(updater.resolve_release()["status"], "ready")
        self.assertNotIn("repos/kropdx/indexx/actions/runs/999", self.calls)

    def test_missing_ci_never_falls_back_to_an_old_commit(self):
        self.runs = []
        result = updater.resolve_release()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["commit"], MAIN)
        self.assertEqual(self.ref_calls, 1)
        self.assertFalse(any(OLD in call for call in self.calls))

    def test_pending_failure_and_non_success_conclusions_block(self):
        for state, conclusion in (("queued", None), ("in_progress", None), ("waiting", None), ("pending", None),
                                  ("completed", "failure"), ("completed", "cancelled"), ("completed", "neutral"),
                                  ("completed", "skipped"), ("completed", "timed_out"), ("completed", None)):
            with self.subTest(state=state, conclusion=conclusion):
                self.ref_calls = 0
                self.details[101] = run_record(status=state, conclusion=conclusion)
                result = updater.resolve_release()
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["ci"]["status"], state)
                self.assertEqual(result["ci"]["conclusion"], conclusion)

    def test_latest_run_failure_blocks_older_success_independent_of_list_order(self):
        self.details[102] = run_record(run_id=102, number=11, conclusion="failure")
        for runs in ([run_record(), self.details[102]], [self.details[102], run_record()]):
            with self.subTest(order=[run["id"] for run in runs]):
                self.ref_calls = 0
                self.runs = runs
                result = updater.resolve_release()
                self.assertEqual(result["status"], "blocked")
                self.assertEqual(result["ci"]["run_id"], 102)

    def test_successful_old_attempt_cannot_hide_pending_rerun(self):
        self.details[101] = run_record(attempt=2, status="queued", conclusion=None)
        result = updater.resolve_release()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["ci"]["run_attempt"], 2)
        self.assertEqual(result["ci"]["status"], "queued")

    def test_successful_latest_rerun_can_supersede_failed_attempt(self):
        self.runs = [run_record(conclusion="failure")]
        self.details[101] = run_record(attempt=2)
        result = updater.resolve_release()
        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["ci"]["run_attempt"], 2)

    def test_stale_or_wrong_run_detail_is_blocked(self):
        self.runs = [run_record(attempt=2)]
        for detail in (run_record(attempt=1), run_record(attempt=2, head_sha=OLD),
                       run_record(attempt=2, run_id=999), run_record(attempt=2, number=9)):
            with self.subTest(detail=detail):
                self.ref_calls = 0
                self.details[101] = detail
                result = updater.resolve_release()
                self.assertEqual(result["status"], "blocked")
                self.assertIn("Current validation run", result["reason"])

    def test_all_pages_are_considered_before_choosing_the_latest_run(self):
        self.runs = [run_record(run_id=1000 + number, number=number) for number in range(1, 102)]
        self.details[1101] = run_record(run_id=1101, number=101, status="queued", conclusion=None)
        result = updater.resolve_release()
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["ci"]["run_id"], 1101)
        self.assertEqual(sum("/runs?" in call for call in self.calls), 2)

    def test_workflow_path_and_attempt_metadata_are_required(self):
        self.workflow["path"] = ".github/workflows/unrelated.yml"
        self.assertEqual(updater.resolve_release()["status"], "blocked")
        self.workflow["path"] = updater.WORKFLOW
        self.ref_calls = 0
        del self.runs[0]["run_attempt"]
        result = updater.resolve_release()
        self.assertEqual(result["status"], "blocked")
        self.assertIn("ordering or attempt", result["reason"])

    def test_workflow_path_with_ref_suffix_is_supported(self):
        self.runs[0]["path"] += "@refs/heads/main"
        self.details[101]["path"] += "@main"
        self.assertEqual(updater.resolve_release()["status"], "ready")

    def test_api_errors_block_without_echoing_credential_related_stderr(self):
        for endpoint in ("/git/ref/", "/actions/workflows/validate.yml", "/runs?", "/actions/runs/"):
            with self.subTest(endpoint=endpoint):
                self.ref_calls = 0
                self.error_at = endpoint
                result = updater.resolve_release()
                self.assertEqual(result["status"], "blocked")
                self.assertIn("GitHub API request failed", result["reason"])
                self.assertNotIn("private authentication detail", json.dumps(result))

    def test_missing_gh_timeout_and_invalid_json_fail_closed(self):
        for outcome in (FileNotFoundError("gh missing"), subprocess.TimeoutExpired("gh", 30),
                        subprocess.CompletedProcess([], 0, stdout="not json", stderr=""),
                        subprocess.CompletedProcess([], 0, stdout="[]", stderr="")):
            with self.subTest(outcome=outcome), mock.patch.object(updater.subprocess, "run") as process:
                if isinstance(outcome, Exception):
                    process.side_effect = outcome
                else:
                    process.return_value = outcome
                self.assertEqual(updater.resolve_release()["status"], "blocked")

    def test_cli_outputs_json_and_nonzero_when_ci_is_blocked(self):
        self.runs = []
        with mock.patch("sys.argv", ["indexx_update.py"]), mock.patch("builtins.print") as output:
            self.assertEqual(updater.main(), 1)
        report = json.loads(output.call_args.args[0])
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["repo"], "kropdx/indexx")
        self.assertEqual(report["commit"], MAIN)


if __name__ == "__main__":
    unittest.main()
