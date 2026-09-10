#!/usr/bin/env python3
"""Build skill and plugin ZIPs from an explicit source-file allowlist."""

import argparse
import json
import re
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
SKILL_NAME = "instagram-saved-ids"
SKILL_FILES = (
    "SKILL.md",
    "agents/openai.yaml",
    "references/browser-collection.md",
    "references/runtime.md",
    "scripts/export_ids.js",
)
PLUGIN_FILES = ("plugin.json", ".codex-plugin/plugin.json", "README.md")


def build(root, output):
    root, output = Path(root).resolve(), Path(output).resolve()
    manifest = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    name, version = manifest["name"], manifest["version"]
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
        raise ValueError("Invalid package name")
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        raise ValueError("Release version must use major.minor.patch")
    legacy = json.loads((root / ".codex-plugin/plugin.json").read_text(encoding="utf-8"))
    for field in ("name", "version", "description", "license", "repository"):
        if legacy.get(field) != manifest.get(field):
            raise ValueError(f"Compatibility manifest differs on {field}")

    skill_dir = root / "skills" / SKILL_NAME
    skill_entries = [(skill_dir / path, f"{SKILL_NAME}/{path}") for path in SKILL_FILES]
    plugin_entries = [(root / path, path) for path in PLUGIN_FILES]
    plugin_entries.extend((skill_dir / path, f"skills/{SKILL_NAME}/{path}") for path in SKILL_FILES)
    if (root / "LICENSE").is_file():
        skill_entries.append((root / "LICENSE", f"{SKILL_NAME}/LICENSE"))
        plugin_entries.append((root / "LICENSE", "LICENSE"))
    elif manifest.get("license"):
        raise ValueError("Manifest declares a license but LICENSE is missing")

    # Check all inputs before opening outputs, and prevent symlink escapes.
    for source, _ in skill_entries + plugin_entries:
        if not source.is_file() or root not in source.resolve().parents:
            raise ValueError(f"Missing or external package input: {source}")
    outputs = [
        (output / f"{SKILL_NAME}-{version}.zip", skill_entries),
        (output / f"{name}-{version}.zip", plugin_entries),
    ]
    output.mkdir(parents=True, exist_ok=True)
    for destination, entries in outputs:
        with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
            for source, archive_name in entries:
                # Fixed metadata makes the same source produce the same ZIP.
                info = ZipInfo(archive_name, date_time=(2020, 1, 1, 0, 0, 0))
                info.create_system = 3
                info.compress_type = ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                archive.writestr(info, source.read_bytes())
    return [path for path, _ in outputs]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, default=ROOT / "dist")
    args = parser.parse_args()
    for path in build(ROOT, args.out_dir):
        print(path)


if __name__ == "__main__":
    main()
