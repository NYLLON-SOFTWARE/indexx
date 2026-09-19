#!/usr/bin/env python3
"""Build the reviewed public source bundle; never inspect a user's library."""

import argparse
import json
from pathlib import Path
import re
import sys


# Changes to the public skill set require explicit review here and in the manifest.
PUBLIC_SKILLS = (
    "indexx-add",
    "indexx-download",
    "indexx-instagram-enrich",
    "indexx-instagram-saves-index",
    "indexx-lint",
    "indexx-progress",
    "indexx-query",
    "indexx-setup",
    "indexx-sync",
    "indexx-transcribe",
    "indexx-wiki-ingest",
)
MANIFEST_PATH = Path("docs/bot-template.json")
OUTPUT_PATH = Path("docs/bot-share-payload.json")


def exact_keys(value, expected, label):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError("{} must contain exactly: {}".format(label, ", ".join(expected)))


def validate_manifest(manifest):
    """Allow only generic, reviewed fields; no live memory or configuration input."""
    exact_keys(manifest, (
        "visibility", "profile", "memory", "skills", "routines", "plugins",
        "gettingStarted",
    ), "public manifest")
    if manifest["visibility"] != "public":
        raise ValueError("public manifest visibility must be public")
    exact_keys(manifest["profile"], (
        "name", "description", "avatarShape", "avatarColor",
    ), "profile")
    for field, value in manifest["profile"].items():
        if not isinstance(value, str) or not value.strip():
            raise ValueError("profile.{} must be a nonempty string".format(field))
    for field in ("memory", "routines", "plugins"):
        if manifest[field] != []:
            raise ValueError("{} must be empty in the public source bundle".format(field))
    if manifest["skills"] != list(PUBLIC_SKILLS):
        raise ValueError("skills must match the reviewed PUBLIC_SKILLS allowlist in order")
    exact_keys(manifest["gettingStarted"], ("skill",), "gettingStarted")
    if manifest["gettingStarted"]["skill"] != "indexx-setup":
        raise ValueError("gettingStarted.skill must be indexx-setup")


def read_source(root, relative):
    path = root / relative
    # A symlink must not redirect a reviewed source to private runtime data.
    if path.resolve() != path:
        raise ValueError("public source cannot be a symlink: {}".format(relative))
    return path.read_text(encoding="utf-8")


def parse_skill(source, label):
    """Read the repository's simple name + folded-description front matter."""
    if not source.startswith("---\n") or "\n---\n" not in source[4:]:
        raise ValueError("{} needs YAML front matter and a body".format(label))
    header, body = source[4:].split("\n---\n", 1)
    fields = {}
    lines = header.splitlines()
    index = 0
    while index < len(lines):
        match = re.fullmatch(r"(name|description): (.+)", lines[index])
        if not match or match.group(1) in fields:
            raise ValueError("{}: use unique name/description fields".format(label))
        key, value = match.groups()
        index += 1
        if value == ">-":
            parts = []
            while index < len(lines) and lines[index].startswith("  "):
                parts.append(lines[index].strip())
                index += 1
            value = " ".join(parts)
        elif value.startswith(('"', "'", "|", ">", "[", "{")):
            raise ValueError("{}: use a plain scalar or >- folded text".format(label))
        if not value.strip():
            raise ValueError("{}: {} cannot be empty".format(label, key))
        fields[key] = value
    exact_keys(fields, ("name", "description"), label + " front matter")
    if not body.strip():
        raise ValueError("{} has no skill body".format(label))
    return fields["description"], body.strip()


def build_payload(root):
    root = Path(root).resolve()
    manifest = json.loads(read_source(root, MANIFEST_PATH))
    validate_manifest(manifest)
    discovered = {path.parent.name for path in (root / "skills").glob("*/SKILL.md")}
    expected = set(PUBLIC_SKILLS)
    if discovered != expected:
        raise ValueError("skill inventory differs from allowlist; missing={}, unreviewed={}".format(
            sorted(expected - discovered), sorted(discovered - expected),
        ))
    skills = []
    for name in PUBLIC_SKILLS:
        relative = Path("skills") / name / "SKILL.md"
        description, content = parse_skill(read_source(root, relative), str(relative))
        skills.append({"name": name, "description": description, "content": content})
    return {**manifest, "skills": skills}


def render_payload(root):
    return json.dumps(build_payload(root), ensure_ascii=False, indent=2) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail if the checked-in bundle differs")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="repository checkout, not a personal library")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    try:
        rendered = render_payload(root)
        destination = root / OUTPUT_PATH
        if destination.resolve() != destination:
            raise ValueError("public bundle destination cannot be a symlink")
        if args.check:
            if not destination.exists() or destination.read_bytes() != rendered.encode("utf-8"):
                print("Public bundle is stale. Run python3 scripts/indexx_export.py.", file=sys.stderr)
                return 1
            print("Public source bundle matches the reviewed manifest and all 11 skills.")
        else:
            destination.write_text(rendered, encoding="utf-8")
            print("Wrote {} from reviewed repository sources.".format(OUTPUT_PATH))
        return 0
    except (OSError, ValueError, UnicodeError) as error:
        print("Export failed: {}".format(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
