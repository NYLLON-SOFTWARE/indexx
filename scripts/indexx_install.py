#!/usr/bin/env python3
"""Install or repair library support files from a clean, pinned source checkout.

Run on the registered Mac after the user chooses the library location.
User data and customized support files are preserved, including on upgrades.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile


SOURCE = Path(__file__).resolve().parent.parent
SUPPORT = ("AGENTS.md", "SCHEMA.md", "README.md", ".gitignore")
RUNTIME_SCRIPTS = ("indexx_status.py", "indexx-status.sh", "indexx_progress.py", "indexx_dashboard.py")
DIRECTORIES = (
    "catalog", "markdown/instagram", "media/instagram", "wiki/sources/instagram",
    "wiki/entities/creators", "wiki/concepts", "wiki/syntheses", "logs", "scripts",
)


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


def load_object(path: Path) -> dict:
    result = json.loads(path.read_text(encoding="utf-8"))
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


def install(source: Path, root: Path, revision: str, refresh: bool = False) -> dict:
    source, root = source.resolve(), root.resolve()
    if root == source or source in root.parents or root in source.parents:
        raise ValueError("Choose a library outside the source checkout")
    defaults = json.loads(source_bytes(source, "examples/.indexx.example.json"))
    if not isinstance(defaults, dict):
        raise ValueError("Default configuration must be a JSON object")
    defaults.update(root=str(root), canonical="mac")
    config_path = destination(root, ".indexx.json")
    current = load_object(config_path) if config_path.exists() else {}
    if "root" in current:
        if not isinstance(current["root"], str) or not current["root"].strip():
            raise ValueError("Existing config root must be a nonempty path; repair it explicitly")
        if Path(current["root"]).expanduser().resolve() != root:
            raise ValueError("Existing config points to another root; request an explicit library relocation")
    config = fill_missing(current, defaults)
    manifest_path = destination(root, "logs/install.json")
    previous = load_object(manifest_path) if manifest_path.exists() else {}
    managed = previous.get("files", {})
    if not isinstance(managed, dict):
        raise ValueError("Invalid installation manifest files map")
    files = {name: source_bytes(source, name) for name in SUPPORT}
    for name in RUNTIME_SCRIPTS:
        files[f"scripts/{name}"] = source_bytes(source, f"scripts/{name}")
    templates = {
        str(path.relative_to(source / "templates")): source_bytes(source, str(path.relative_to(source)))
        for path in sorted((source / "templates/wiki").rglob("*.md"))
    }
    paths = config["paths"]
    selector = paths.get("use_catalog", "legacy")
    if selector not in ("legacy", "catalog"):
        raise ValueError("paths.use_catalog must be legacy or catalog")
    catalog = paths["instagram_catalog_legacy" if selector == "legacy" else "instagram_catalog"]
    if not isinstance(catalog, str) or Path(catalog).is_absolute() or ".." in Path(catalog).parts:
        raise ValueError("Configured catalog must be a relative path inside the library")
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
    report = {"source_revision": revision, "created": [], "updated": [], "preserved": [], "conflicts": []}
    new_managed = dict(managed)
    for relative in DIRECTORIES:
        destination(root, relative).mkdir(parents=True, exist_ok=True)
    for relative, content in files.items():
        target = destination(root, relative)
        existing = target.read_bytes() if target.exists() else None
        if existing is None:
            atomic_write(target, content)
            report["created"].append(relative)
            new_managed[relative] = digest(content)
        elif existing == content:
            new_managed[relative] = digest(content)
        elif refresh and managed.get(relative) == digest(existing):
            atomic_write(target, content)
            report["updated"].append(relative)
            new_managed[relative] = digest(content)
        else:
            report["conflicts" if refresh else "preserved"].append(relative)
    # Templates become user data once installed; never overwrite them on repair.
    for relative, content in templates.items():
        target = destination(root, relative)
        if not target.exists():
            atomic_write(target, content)
            report["created"].append(relative)
    atomic_write(config_path, (json.dumps(config, indent=2) + "\n").encode())
    atomic_write(manifest_path, (json.dumps({"source_revision": revision, "files": new_managed}, indent=2) + "\n").encode())
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="User-confirmed absolute library path")
    parser.add_argument("--revision", required=True, help="Reviewed full Git commit ID")
    parser.add_argument("--check", action="store_true", help="Check local prerequisites and source; do not install")
    parser.add_argument("--refresh-support", action="store_true", help="Upgrade previously managed, unmodified support files")
    args = parser.parse_args()
    try:
        root = Path(args.root).expanduser()
        if not root.is_absolute():
            raise ValueError("--root must be an absolute path chosen by the user")
        revision = source_revision(SOURCE, args.revision)
        problems = preflight(root)
        if problems:
            for problem in problems:
                print(problem, file=sys.stderr)
            return 2
        if args.check:
            print(f"Ready to install revision {revision} at {root}")
            return 0
        report = install(SOURCE, root, revision, args.refresh_support)
        print(json.dumps(report, indent=2))
        return 1 if report["conflicts"] else 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"Setup stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
