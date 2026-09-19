#!/usr/bin/env python3
"""Resolve a trusted INDEXX commit and its latest successful main/push validation.

Read-only: uses the authenticated GitHub CLI without handling credentials, cloning,
installing, or changing a library. Pending, missing, or failed evidence blocks an
update; an older green commit is never substituted for the resolved main commit.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from typing import Optional
from urllib.parse import urlencode


REPO = "NYLLON-SOFTWARE/indexx"
CHANNEL = "main"
WORKFLOW = ".github/workflows/validate.yml"
SHA = re.compile(r"[0-9a-fA-F]{40}\Z")


def gh_json(endpoint: str) -> dict:
    """The only external boundary; gh owns authentication and sends a GET request."""
    command = ["gh", "api", "--hostname", "github.com", "--method", "GET",
               "-H", "Accept: application/vnd.github+json", endpoint]
    try:
        response = subprocess.run(command, capture_output=True, text=True, timeout=30)
    except FileNotFoundError as exc:
        raise ValueError("GitHub CLI is unavailable; install gh and authenticate for repository access") from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("GitHub API is unavailable; retry when authenticated GitHub access is working") from exc
    if response.returncode:
        # Do not echo subprocess output that could contain authentication details.
        raise ValueError(f"GitHub API request failed (gh exit {response.returncode}); check authentication and repository access")
    try:
        value = json.loads(response.stdout)
    except ValueError as exc:
        raise ValueError("GitHub API returned invalid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("GitHub API returned an unexpected response shape")
    return value


def positive_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def matches(run: dict, commit: str, workflow_id: int) -> bool:
    repository, head_repository = run.get("repository"), run.get("head_repository")
    def trusted(value: object) -> bool:
        return (isinstance(value, dict) and isinstance(value.get("full_name"), str)
                and value["full_name"].casefold() == REPO.casefold())
    return (
        run.get("head_sha") == commit and run.get("head_branch") == CHANNEL
        and run.get("event") == "push" and run.get("workflow_id") == workflow_id
        and isinstance(run.get("path"), str) and run["path"].split("@", 1)[0] == WORKFLOW
        and trusted(repository) and trusted(head_repository)
    )


def workflow_runs(commit: str, workflow_id: int) -> list[dict]:
    """Read every page without filtering on success, so newer failures remain visible."""
    runs, total, page = [], None, 1
    while total is None or len(runs) < total:
        query = urlencode({"branch": CHANNEL, "event": "push", "head_sha": commit,
                           "per_page": 100, "page": page})
        response = gh_json(f"repos/{REPO}/actions/workflows/{workflow_id}/runs?{query}")
        reported = response.get("total_count")
        if not isinstance(reported, int) or isinstance(reported, bool) or not 0 <= reported <= 1000:
            raise ValueError("Cannot establish the latest validation run from the API result count")
        if total is not None and reported != total:
            raise ValueError("Validation run list changed during lookup; retry the update check")
        total = reported
        batch = response.get("workflow_runs")
        if not isinstance(batch, list) or not all(isinstance(run, dict) for run in batch):
            raise ValueError("GitHub API returned an invalid workflow run list")
        if not batch and len(runs) < total:
            raise ValueError("GitHub API returned an incomplete workflow run list")
        runs.extend(batch)
        if len(runs) > total:
            raise ValueError("GitHub API workflow run count is inconsistent")
        page += 1
    return runs


def latest_run(commit: str, workflow_id: int) -> dict:
    candidates = [run for run in workflow_runs(commit, workflow_id) if matches(run, commit, workflow_id)]
    if not candidates:
        raise ValueError("No validation push run on main was found for this exact commit")
    if not all(all(positive_int(run.get(key)) for key in ("id", "run_number", "run_attempt")) for run in candidates):
        raise ValueError("Validation run ordering or attempt evidence is missing")
    return max(candidates, key=lambda run: (run["run_number"], run["id"], run["run_attempt"]))


def resolve_release(revision: Optional[str] = None) -> dict:
    report = {"status": "blocked", "repo": REPO, "channel": CHANNEL, "commit": None,
              "main_commit": None, "ci": {"workflow": WORKFLOW}, "reason": None}
    try:
        if revision is not None and (not isinstance(revision, str) or not SHA.fullmatch(revision)):
            raise ValueError("--revision must be a full 40-character Git commit ID")
        # Resolve the moving ref exactly once. Every later request uses this snapshot.
        ref = gh_json(f"repos/{REPO}/git/ref/heads/{CHANNEL}")
        target = ref.get("object")
        if (ref.get("ref") != f"refs/heads/{CHANNEL}" or not isinstance(target, dict)
                or target.get("type") != "commit" or not isinstance(target.get("sha"), str)
                or not SHA.fullmatch(target["sha"])):
            raise ValueError("GitHub did not return a valid main commit")
        main_commit = target["sha"].lower()
        commit = revision.lower() if revision is not None else main_commit
        report.update(commit=commit, main_commit=main_commit)
        if commit != main_commit:
            comparison = gh_json(f"repos/{REPO}/compare/{commit}...{main_commit}")
            base, merge_base = comparison.get("base_commit"), comparison.get("merge_base_commit")
            if (comparison.get("status") != "ahead" or not isinstance(base, dict)
                    or base.get("sha") != commit or not isinstance(merge_base, dict)
                    or merge_base.get("sha") != commit):
                raise ValueError("Requested revision is not verified as reachable from the resolved main commit")
        workflow = gh_json(f"repos/{REPO}/actions/workflows/validate.yml")
        workflow_id = workflow.get("id")
        if workflow.get("path") != WORKFLOW or not positive_int(workflow_id):
            raise ValueError("GitHub did not return the trusted repository validation workflow")
        latest = latest_run(commit, workflow_id)
        # The list may still describe an old successful attempt while a rerun starts.
        # Fetch the selected run's current attempt instead of reusing that conclusion.
        current = gh_json(f"repos/{REPO}/actions/runs/{latest['id']}")
        if (not matches(current, commit, workflow_id) or current.get("id") != latest["id"]
                or current.get("run_number") != latest["run_number"]
                or not positive_int(current.get("run_attempt")) or current["run_attempt"] < latest["run_attempt"]):
            raise ValueError("Current validation run does not match the selected commit, workflow, or latest attempt")
        report["ci"].update({"workflow_id": workflow_id, "run_id": current["id"],
                             "run_number": current["run_number"], "run_attempt": current["run_attempt"],
                             "event": current["event"], "branch": current["head_branch"],
                             "commit": current["head_sha"], "status": current.get("status"),
                             "conclusion": current.get("conclusion"),
                             "url": f"https://github.com/{REPO}/actions/runs/{current['id']}/attempts/{current['run_attempt']}"})
        if current.get("status") != "completed" or current.get("conclusion") != "success":
            raise ValueError("Latest validation run/attempt for this exact commit is not completed successfully")
        # A different run can start while the selected run's detail is fetched.
        # Re-list once rather than chasing changes or trusting an older green run.
        # This verifies an observed snapshot, not a guarantee about future CI state.
        refreshed = latest_run(commit, workflow_id)
        if any(refreshed[key] != current[key] for key in ("id", "run_number", "run_attempt")):
            raise ValueError("Latest validation run/attempt changed during lookup; retry the update check")
        report["ci"].update(status=refreshed.get("status"), conclusion=refreshed.get("conclusion"))
        if refreshed.get("status") != "completed" or refreshed.get("conclusion") != "success":
            raise ValueError("Refreshed validation run/attempt is not completed successfully")
        report.update(status="ready", reason=None)
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        report["reason"] = str(exc)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", help="Optional historical full commit reachable from main")
    args = parser.parse_args()
    report = resolve_release(args.revision)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "ready" else 1


if __name__ == "__main__":
    raise SystemExit(main())
