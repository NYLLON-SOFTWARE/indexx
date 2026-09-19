#!/usr/bin/env python3
"""Install or repair library support files from a clean, pinned source checkout.

Run on the registered Mac after the user chooses the library location.
User data and customized support files are preserved, including on upgrades.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid


SOURCE = Path(__file__).resolve().parent.parent
SUPPORT = ("AGENTS.md", "SCHEMA.md", "README.md", ".gitignore")
RUNTIME_SCRIPTS = ("indexx_status.py", "indexx-status.sh", "indexx_progress.py", "indexx_dashboard.py")
DIRECTORIES = (
    "catalog", "markdown/instagram", "media/instagram", "wiki/sources/instagram",
    "wiki/entities/creators", "wiki/concepts", "wiki/syntheses", "logs", "scripts",
)
SUPPORT_PATHS = SUPPORT + tuple(f"scripts/{name}" for name in RUNTIME_SCRIPTS)

# Load this checkout's parser, not a possibly stale helper in the target library.
# A file import also supports callers that load this installer with importlib.
_status_spec = importlib.util.spec_from_file_location("indexx_install_status", SOURCE / "scripts/indexx_status.py")
_status = importlib.util.module_from_spec(_status_spec)
_status_spec.loader.exec_module(_status)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_bytes(source: Path, relative: str) -> bytes:
    path = source / relative
    if path.resolve() != path:
        raise ValueError(f"Installation source must not redirect through a symlink: {relative}")
    return path.read_bytes()


def destination(root: Path, relative: str) -> Path:
    path = root / relative
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        raise ValueError(f"Library path escapes the chosen root: {relative}")
    return path


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def load_object(path: Path, data: bytes = None) -> dict:
    result = _status.strict_json(path.read_text(encoding="utf-8") if data is None else data.decode("utf-8"))
    if not isinstance(result, dict):
        raise ValueError(f"Expected a JSON object: {path.name}")
    return result


def fill_missing(current: dict, defaults: dict) -> dict:
    """Repair absent configuration fields without replacing user choices."""
    result = dict(current)
    for key, value in defaults.items():
        if key not in result:
            result[key] = value
        elif isinstance(value, dict):
            if not isinstance(result[key], dict):
                raise ValueError(f"Configuration field {key} must be an object")
            result[key] = fill_missing(result[key], value)
    return result


def source_revision(source: Path, requested: str) -> str:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", requested):
        raise ValueError("--revision must be a full 40-character Git commit ID")
    def git(*args: str) -> str:
        return subprocess.check_output(
            ["git", "-C", str(source), *args], text=True, stderr=subprocess.PIPE
        ).strip()
    if Path(git("rev-parse", "--show-toplevel")).resolve() != source.resolve():
        raise ValueError("Run the installer from the source repository checkout")
    actual = git("rev-parse", "HEAD")
    if actual.lower() != requested.lower():
        raise ValueError(f"Source checkout is {actual}, not requested revision {requested}")
    dirty = git("status", "--porcelain", "--untracked-files=all", "--",
                *SUPPORT, "scripts", "templates", "examples")
    if dirty:
        raise ValueError("Installation source has uncommitted changes; use a clean pinned checkout")
    return actual


def preflight(root: Path) -> list[str]:
    problems = []
    if sys.platform != "darwin":
        problems.append("This release supports a registered macOS computer; Windows/Linux are unverified")
    if sys.version_info < (3, 9):
        problems.append("Python 3.9 or newer is required")
    for tool in ("ffmpeg", "ffprobe", "rg"):
        if shutil.which(tool) is None:
            problems.append(f"Missing local tool: {tool}")
    parent = root
    while not parent.exists():
        parent = parent.parent
    if not parent.is_dir():
        problems.append(f"Library location is not a directory: {parent}")
    else:
        try:
            with tempfile.TemporaryFile(dir=parent):
                pass
        except OSError as exc:
            problems.append(f"Library location is not writable: {exc}")
    return problems


def catalog_path(root: Path, raw: str) -> str:
    """Keep catalogs away from configuration, executable support, and other data."""
    root = root.resolve()
    if (not isinstance(raw, str) or not raw.strip() or Path(raw).is_absolute()
            or ".." in Path(raw).parts or Path(raw) == Path(".")):
        raise ValueError("Configured catalog must be a relative path inside the library")
    path = Path(raw)
    resolved = destination(root, raw).resolve().relative_to(root)
    # macOS commonly uses a case-insensitive filesystem.
    reserved = tuple(Path(p.casefold()) for p in (*SUPPORT_PATHS, ".indexx.json", "logs", "scripts", "media", "wiki", ".git", ".codex", ".agents"))
    for candidate in (path, resolved):
        candidate = Path(str(candidate).casefold())
        if any(candidate == directory or candidate in directory.parents for directory in map(Path, DIRECTORIES)):
            raise ValueError(f"Configured catalog collides with a library directory: {raw}")
        if any(candidate == target or target in candidate.parents or candidate in target.parents for target in reserved):
            raise ValueError(f"Configured catalog collides with a reserved library path: {raw}")
    return str(path)


def _plan(source: Path, root: Path, revision: str, refresh: bool, replace_support: tuple[str, ...]) -> tuple[dict, dict]:
    source, root = source.resolve(), root.resolve()
    if root == source or source in root.parents or root in source.parents:
        raise ValueError("Choose a library outside the source checkout")
    for relative in replace_support:
        if relative not in SUPPORT_PATHS:
            raise ValueError(f"--replace-support accepts only a support file's exact relative path: {relative}")
    defaults = json.loads(source_bytes(source, "examples/.indexx.example.json"))
    if not isinstance(defaults, dict):
        raise ValueError("Default configuration must be a JSON object")
    defaults.update(root=str(root), canonical="mac")
    observed = {}
    def observe(relative):
        path = destination(root, relative)
        value = path.read_bytes() if path.exists() else None
        observed[relative] = value
        return value
    config_path = destination(root, ".indexx.json")
    config_before = observe(".indexx.json")
    current = load_object(config_path, config_before) if config_before is not None else {}
    if "root" in current:
        if not isinstance(current["root"], str) or not current["root"].strip():
            raise ValueError("Existing config root must be a nonempty path; repair it explicitly")
        if Path(current["root"]).expanduser().resolve() != root:
            raise ValueError("Existing config points to another root; request an explicit library relocation")
    config = fill_missing(current, defaults)
    manifest_path = destination(root, "logs/install.json")
    manifest_before = observe("logs/install.json")
    previous = load_object(manifest_path, manifest_before) if manifest_before is not None else {}
    managed = previous.get("files", {})
    if not isinstance(managed, dict):
        raise ValueError("Invalid installation manifest files map")
    files = {name: source_bytes(source, name) for name in SUPPORT_PATHS}
    templates = {
        str(path.relative_to(source / "templates")): source_bytes(source, str(path.relative_to(source)))
        for path in sorted((source / "templates/wiki").rglob("*.md"))
    }
    paths = config["paths"]
    selector = paths.get("use_catalog", "legacy")
    if selector not in ("legacy", "catalog"):
        raise ValueError("paths.use_catalog must be legacy or catalog")
    for key in ("instagram_catalog_legacy", "instagram_catalog"):
        catalog_path(root, paths[key])
    catalog = catalog_path(root, paths["instagram_catalog_legacy" if selector == "legacy" else "instagram_catalog"])
    templates[catalog] = source_bytes(source, "examples/saves-index.example.md")
    # Validate every target before creating anything, including symlink ancestors.
    for relative in (*DIRECTORIES, *files, *templates, ".indexx.json", "logs/install.json"):
        target = destination(root, relative)
        for parent in target.parents:
            if parent.exists() and not parent.is_dir():
                raise ValueError(f"Expected a directory at {parent}")
            if parent == root:
                break
        if relative in DIRECTORIES and target.exists() and not target.is_dir():
            raise ValueError(f"Expected a directory at {relative}")
        if relative in (*files, *templates, ".indexx.json", "logs/install.json") and target.exists() and not target.is_file():
            raise ValueError(f"Expected a file at {relative}")
    report = {
        "status": "ready", "requested_revision": revision,
        "planned": {"create": [], "update": [], "replace": [], "adopt": []},
        "created": [], "updated": [], "replaced": [], "conflicts": [],
        "conflict_details": [], "migration_required": [], "next_steps": [],
        "artifact_audit": "not_run",
    }
    catalog_before = observe(catalog)
    try:
        _status.parse_catalog(catalog_before.decode("utf-8") if catalog_before is not None else templates[catalog].decode("utf-8"))
    except ValueError as exc:
        report["migration_required"].append(f"{catalog}: {exc}")
    stt = config["stt"]
    if stt.get("provider") not in (None, "grok", "elevenlabs") or "primary" in stt or "fallback" in stt:
        report["migration_required"].append("stt must use provider grok, elevenlabs, or null, without legacy primary/fallback fields; preserve the user's choice during migration")
    writes, replaced, new_managed = {}, {}, {}
    for relative, content in files.items():
        existing = observe(relative)
        if existing is None:
            report["planned"]["create"].append(relative)
            writes[relative] = content
        elif existing == content:
            if managed.get(relative) != digest(content):
                report["planned"]["adopt"].append(relative)
        elif relative in replace_support:
            report["planned"]["replace"].append(relative)
            replaced[relative] = existing
            writes[relative] = content
        elif refresh and managed.get(relative) == digest(existing):
            report["planned"]["update"].append(relative)
            writes[relative] = content
        else:
            reason = "unmanaged" if relative not in managed else "modified-managed"
            if managed.get(relative) == digest(existing):
                reason = "managed-needs-refresh"
            report["conflicts"].append(relative)
            report["conflict_details"].append({"path": relative, "reason": reason})
        new_managed[relative] = digest(content)
    # Templates become user data once installed; never overwrite them on repair.
    for relative, content in templates.items():
        target = destination(root, relative)
        if not target.exists():
            observed.setdefault(relative, None)
            writes[relative] = content
            report["planned"]["create"].append(relative)
    if report["migration_required"]:
        report["next_steps"].append("Run python3 scripts/indexx_migrate.py --root <library-root> from this pinned source checkout to review a migration plan, then follow its instructions.")
    if report["conflicts"]:
        report["next_steps"].append("Diff each listed file against the pinned source. Use --refresh-support for unchanged managed files; after reviewing an unmanaged or modified file, authorize only that replacement with --replace-support PATH (repeatable). Replacements are backed up locally.")
    if report["migration_required"] or report["conflicts"]:
        report["status"] = "blocked"
    if replaced:
        backup_parent = destination(root, "logs/install-backups")
        if backup_parent.exists() and not backup_parent.is_dir():
            raise ValueError("Expected a directory at logs/install-backups")
    prepared = {"root": root, "writes": writes, "replaced": replaced, "config": config,
                "managed": new_managed, "observed": observed}
    return report, prepared


def require_unchanged(root: Path, observed: dict) -> None:
    """Stop if any planned input changed; never back up stale planned bytes."""
    for relative, expected in observed.items():
        target = destination(root, relative)
        current = target.read_bytes() if target.exists() else None
        if current != expected:
            raise ValueError(f"Library file changed during installation: {relative}; stop other writers and re-plan")


def plan(source: Path, root: Path, revision: str, refresh: bool = False, replace_support: tuple[str, ...] = ()) -> dict:
    """Report compatibility and every support-file conflict without modifying the library."""
    return _plan(source, root, revision, refresh, replace_support)[0]


def install(source: Path, root: Path, revision: str, refresh: bool = False, replace_support: tuple[str, ...] = ()) -> dict:
    report, prepared = _plan(source, root, revision, refresh, replace_support)
    if report["status"] == "blocked":
        return report
    root = prepared["root"]
    observed = prepared["observed"]
    require_unchanged(root, observed)
    if prepared["replaced"]:
        backup = "logs/install-backups/" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ-") + uuid.uuid4().hex
        # Back up every explicit replacement before replacing any file.
        for relative, content in prepared["replaced"].items():
            require_unchanged(root, {relative: observed[relative]})
            atomic_write(destination(root, f"{backup}/{relative}"), content)
        report["backup_path"] = backup
    require_unchanged(root, observed)
    for relative in DIRECTORIES:
        destination(root, relative).mkdir(parents=True, exist_ok=True)
    for relative, content in prepared["writes"].items():
        require_unchanged(root, {relative: observed[relative]})
        atomic_write(destination(root, relative), content)
        observed[relative] = content
    require_unchanged(root, observed)
    config_content = (json.dumps(prepared["config"], indent=2) + "\n").encode()
    atomic_write(destination(root, ".indexx.json"), config_content)
    observed[".indexx.json"] = config_content
    require_unchanged(root, observed)
    atomic_write(destination(root, "logs/install.json"), (json.dumps({"source_revision": revision, "files": prepared["managed"]}, indent=2) + "\n").encode())
    report.update(status="installed", source_revision=revision,
                  created=report["planned"]["create"], updated=report["planned"]["update"], replaced=report["planned"]["replace"])
    report["next_steps"].append("Support files are installed at the requested revision. Run scripts/indexx_status.py for a separate library artifact audit; this installer has not validated item completion.")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="User-confirmed absolute library path")
    parser.add_argument("--revision", required=True, help="Reviewed full Git commit ID")
    parser.add_argument("--check", action="store_true", help="Plan prerequisites, compatibility, and file changes without installing")
    parser.add_argument("--refresh-support", action="store_true", help="Upgrade previously managed, unmodified support files")
    parser.add_argument("--replace-support", action="append", default=[], metavar="PATH", help="After reviewing a diff, replace this exact support file and back up its previous contents; repeat for each authorized file")
    args = parser.parse_args()
    try:
        root = Path(args.root).expanduser()
        if not root.is_absolute():
            raise ValueError("--root must be an absolute path chosen by the user")
        revision = source_revision(SOURCE, args.revision)
        report = plan(SOURCE, root, revision, args.refresh_support, tuple(args.replace_support))
        problems = preflight(root)
        if problems:
            report.update(status="blocked", prerequisite_errors=problems)
            print(json.dumps(report, indent=2))
            return 2
        if not args.check and report["status"] != "blocked":
            report = install(SOURCE, root, revision, args.refresh_support, tuple(args.replace_support))
        print(json.dumps(report, indent=2))
        return 1 if report["status"] == "blocked" else 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Setup stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
