#!/usr/bin/env python3
"""Local, rebuildable full-text and explicit-person search (Python 3.9+, SQLite FTS5).

Only catalog, JSON metadata and markdown are read. No media bytes, network calls,
identity inference, or changes to source documents. Stop other library writers
while building. Query refuses a stale cache instead of silently returning it.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sqlite3
import sys
import tempfile
import unicodedata
from typing import Optional

import indexx_status as status

CACHE = "db/search.sqlite3"
VERSION = 4
APPLICATION_ID = 0x49445858
ROLES = {"speaker", "featured", "mentioned"}


def _root(root: Path) -> Path:
    root = root.expanduser()
    if not root.is_absolute() or not root.is_dir():
        raise ValueError("--root must be an existing absolute library directory")
    return root.resolve()


def _safe(root: Path, raw: str) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise ValueError("Expected a nonempty library path")
    supplied = Path(raw).expanduser()
    path = supplied if supplied.is_absolute() else root / supplied
    if ".." in supplied.parts:
        raise ValueError("Parent traversal is not allowed")
    try:
        relative = path.relative_to(root)
        path.resolve().relative_to(root)
    except ValueError as exc:
        raise ValueError("Path escapes the library") from exc
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Symlink inputs and cache paths are not supported")
        if current != path and current.exists() and not current.is_dir():
            raise ValueError("Path parent is not a directory")
    return path


def _key(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def _signature(root: Path, relative: str) -> str:
    try:
        path = _safe(root, relative)
        if not path.exists():
            return "missing"
        info = path.stat()
        return json.dumps([info.st_dev, info.st_ino, info.st_mode, info.st_size,
                           info.st_mtime_ns, info.st_ctime_ns])
    except (OSError, ValueError) as exc:
        return "unsafe:" + str(exc)


def _wiki_listing(root: Path) -> list[str]:
    try:
        base = _safe(root, "wiki")
        if not base.exists():
            return []
        if not base.is_dir():
            return ["wiki/"]
        result = []
        for directory, subdirs, files in os.walk(base, followlinks=False):
            for name in list(subdirs):
                path = Path(directory) / name
                relative = path.relative_to(root).as_posix()
                if relative.casefold() == "wiki/views":
                    subdirs.remove(name)
                elif path.is_symlink():
                    result.append(relative + "/")
                    subdirs.remove(name)
            result.extend((Path(directory) / name).relative_to(root).as_posix()
                          for name in files if name.casefold().endswith(".md"))
        return sorted(result)
    except (OSError, ValueError):
        return ["wiki/"]


class Inputs:
    def __init__(self, root: Path):
        self.root = root
        self.manifest: dict = {}
        self.warnings: list[str] = []

    def warn(self, relative: str, error: object) -> None:
        self.warnings.append(f"{relative}: {error}")

    def text(self, relative: str, required: bool = False) -> Optional[str]:
        self.manifest[relative] = _signature(self.root, relative)
        try:
            path = _safe(self.root, relative)
            if not path.exists():
                if required:
                    raise ValueError("Required input is missing")
                return None
            if not path.is_file():
                raise ValueError("Expected a regular text file")
            data = path.read_bytes()
            if _signature(self.root, relative) != self.manifest[relative]:
                raise ValueError("Input changed while being read; rebuild after other writers stop")
            return data.decode("utf-8")
        except (OSError, ValueError) as exc:
            if required:
                raise ValueError(f"{relative}: {exc}") from exc
            self.warn(relative, exc)
            return None

    def video(self, relative: str) -> Optional[str]:
        # Availability is checked with stat, never by opening media bytes.
        self.manifest[relative] = _signature(self.root, relative)
        try:
            path = _safe(self.root, relative)
            return relative if path.is_file() and path.stat().st_size else None
        except (OSError, ValueError) as exc:
            self.warn(relative, exc)
            return None

    def wiki(self) -> dict[str, str]:
        listing = _wiki_listing(self.root)
        self.manifest["@wiki_listing"] = listing
        documents = {}
        for relative in listing:
            text = self.text(relative)
            if text is not None:
                documents[relative] = text
        return documents


def _current_manifest(root: Path, previous: dict) -> dict:
    return {relative: _wiki_listing(root) if relative == "@wiki_listing" else _signature(root, relative)
            for relative in previous}


def _document(text: str) -> tuple[dict, str]:
    return status.frontmatter(text) if text.startswith("---\n") or text.startswith("---\r\n") else ({}, text)


def _title(front: dict, body: str, fallback: str) -> str:
    if isinstance(front.get("title"), str) and front["title"].strip():
        return front["title"].strip()
    heading = re.search(r"^#\s+(.+)$", body, re.M)
    return heading.group(1).strip() if heading else fallback


def _snapshot(root: Path) -> tuple[Inputs, list[dict], list[dict], dict, dict]:
    inputs = Inputs(root)
    config = status.strict_json(inputs.text(".indexx.json", required=True))
    if not isinstance(config, dict) or not isinstance(config.get("paths"), dict):
        raise ValueError("Config requires a paths object")
    paths = config["paths"]
    selector = paths.get("use_catalog")
    if selector not in ("legacy", "catalog"):
        raise ValueError("paths.use_catalog must be legacy or catalog")
    catalog_path = _safe(root, paths.get("instagram_catalog_legacy" if selector == "legacy" else "instagram_catalog"))
    catalog_relative = catalog_path.relative_to(root).as_posix()
    if catalog_relative == CACHE or (root / "db") in catalog_path.parents:
        raise ValueError("Catalog collides with search cache storage")
    rows = status.parse_catalog(inputs.text(catalog_relative, required=True))
    documents = inputs.wiki()
    persons = {}
    wiki_results = []
    for relative, text in documents.items():
        if not relative.startswith(("wiki/entities/", "wiki/concepts/", "wiki/syntheses/")):
            continue
        try:
            front, body = _document(text)
            if relative.startswith("wiki/entities/people/"):
                slug = Path(relative).stem
                _safe(root, f"wiki/entities/people/{slug}.md")
                persons[slug] = status.person_page(root, slug)
            wiki_results.append({"path": relative, "title": _title(front, body, Path(relative).stem), "body": body})
        except (OSError, ValueError) as exc:
            inputs.warn(relative, exc)
    items = []
    source_count = reviewed_count = 0
    for row in rows:
        item_id = row["shortcode"]
        item = {"id": item_id, "platform": "instagram", "title": row.get("title") or item_id,
                "url": row["url"], "handle": row.get("handle", "").lstrip("@"),
                "type": "video" if row["type"] == "reel" else row["type"], "catalog_type": row["type"],
                "status": row["status"], "media_path": None,
                "video_path": None, "source_path": None, "people": [], "body": ""}
        # Index content fields explicitly: URLs, status, paths and other operational
        # columns are not prose and otherwise make boilerplate match every clip.
        indexed_extra = [row.get("title", "")]
        text_parts = [row.get(field, "") for field in ("caption", "caption_snippet", "description", "notes", "note")]
        if status.instagram_id(row["url"]) != item_id:
            inputs.warn(item_id, "Catalog URL does not match item identity")
            item["url"] = None
        if row["media_path"]:
            inputs.manifest[row["media_path"]] = _signature(root, row["media_path"])
            try:
                path = _safe(root, row["media_path"])
                folder = path.parent if path.is_file() else path
                folder.relative_to(root / "media/instagram")
                relative = folder.relative_to(root).as_posix()
                item["media_path"] = path.relative_to(root).as_posix()
                info_text = inputs.text(relative + "/info.json")
                if info_text is None:
                    raise ValueError("Metadata unavailable; media text and video links are omitted")
                info = status.strict_json(info_text)
                if (not isinstance(info, dict) or info.get("platform") != "instagram"
                        or info.get("id", info.get("shortcode")) != item_id
                        or status.instagram_id(info.get("source_url", info.get("url"))) != item_id):
                    raise ValueError("info.json identity does not match catalog")
                if info.get("type") in ("video", "image", "carousel"):
                    item["type"] = info["type"]
                handle = info.get("handle")
                if isinstance(handle, str) and status.HANDLE_PATTERN.fullmatch(handle) and handle not in (".", ".."):
                    if item["handle"] and _key(item["handle"]) != _key(handle):
                        inputs.warn(item_id, "Catalog uploader differs from metadata; catalog uploader retained")
                    else:
                        item["handle"] = handle
                for field in ("caption", "title", "description"):
                    if isinstance(info.get(field), str):
                        (indexed_extra if field == "title" else text_parts).append(info[field])
                if not row.get("title") and isinstance(info.get("title"), str) and info["title"].strip():
                    item["title"] = info["title"].strip()
                transcript = inputs.text(relative + "/transcript.md")
                if transcript:
                    try:
                        _, transcript_body = _document(transcript)
                    except ValueError as exc:
                        inputs.warn(relative + "/transcript.md", exc)
                        transcript_body = transcript
                    text_parts.append(transcript_body)
                item["video_path"] = inputs.video(relative + "/media.mp4")
            except (OSError, ValueError) as exc:
                inputs.warn(item_id, exc)
        source_relative = f"wiki/sources/instagram/{item_id}.md"
        source = documents.get(source_relative)
        if source is not None:
            try:
                front, body = status.frontmatter(source)
                if front.get("id") != item_id or front.get("platform") != "instagram":
                    raise ValueError("Wiki source identity does not match catalog")
                source_handle = front.get("handle")
                if item["handle"] and (not isinstance(source_handle, str) or _key(source_handle) != _key(item["handle"])):
                    raise ValueError("Wiki source uploader does not match catalog/metadata")
                if not item["handle"] and isinstance(source_handle, str) and status.HANDLE_PATTERN.fullmatch(source_handle):
                    item["handle"] = source_handle
                item["source_path"] = source_relative
                source_count += 1
                text_parts.append(body)
                item["title"] = _title(front, body, item["title"])
                # Classification and people are independent optional annotations.
                if "tags" in front or "facets" in front:
                    try:
                        status.classification(front)
                        indexed_extra.append(json.dumps({"tags": front["tags"], "facets": front["facets"]}, ensure_ascii=False))
                    except ValueError as exc:
                        inputs.warn(source_relative, exc)
                # Validate referenced person paths before the shared validator reads pages.
                annotations = front.get("people", [])
                if isinstance(annotations, list):
                    for annotation in annotations:
                        if isinstance(annotation, dict) and isinstance(annotation.get("id"), str):
                            slug = annotation["id"]
                            if not status.SLUG_PATTERN.fullmatch(slug):
                                raise ValueError("Invalid person id")
                            _safe(root, f"wiki/entities/people/{slug}.md")
                item["people"] = status.person_annotations(front, root)
                for annotation in item["people"]:
                    canonical = persons.get(annotation["id"])
                    if canonical is not None:
                        indexed_extra.extend([annotation["id"], canonical["name"], *canonical.get("aliases", [])])
                if front.get("people_reviewed") is True:
                    reviewed_count += 1
            except (OSError, ValueError) as exc:
                inputs.warn(source_relative, exc)
        item["body"] = "\n\n".join(part for part in text_parts if part)
        item["search_text"] = "\n".join([item["title"], item["body"], *indexed_extra])
        items.append(item)
    coverage = {"catalog_total": len(items), "wiki_sources": source_count,
                "people_reviewed": reviewed_count, "unreviewed": len(items) - reviewed_count}
    return inputs, items, wiki_results, persons, coverage


def _cache(root: Path) -> Path:
    cache = _safe(root, CACHE)
    if cache.exists() and not cache.is_file():
        raise ValueError("Search cache path collides with a directory")
    return cache


def _connect(cache: Path) -> sqlite3.Connection:
    if not cache.is_file():
        raise ValueError("Search index is missing; run indexx_search.py build --root <root>")
    connection = sqlite3.connect(cache.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        if connection.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
            raise ValueError("Cache path contains an unrecognized database; refusing to use or replace it")
        connection.execute("PRAGMA query_only = ON")
        return connection
    except Exception:
        connection.close()
        raise


def build_index(root: Path) -> dict:
    root = _root(root)
    cache = _cache(root)
    if cache.exists():
        _connect(cache).close()
    inputs, items, wiki_pages, persons, coverage = _snapshot(root)
    metadata = {"version": VERSION, "manifest": inputs.manifest, "coverage": coverage,
                "warnings": inputs.warnings, "indexed_at": datetime.now(timezone.utc).isoformat()}
    cache.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".search-", suffix=".sqlite3", dir=cache.parent)
    os.close(fd)
    try:
        db = sqlite3.connect(temporary)
        try:
            db.executescript(f"""
                PRAGMA application_id = {APPLICATION_ID};
                CREATE TABLE metadata (data TEXT NOT NULL);
                CREATE TABLE items (id TEXT PRIMARY KEY, handle TEXT, type TEXT, data TEXT);
                CREATE VIRTUAL TABLE item_text USING fts5(id UNINDEXED, body, tokenize='unicode61');
                CREATE TABLE people (item_id TEXT, person_id TEXT, role TEXT);
                CREATE INDEX people_lookup ON people(person_id, role, item_id);
                CREATE TABLE person_names (person_id TEXT, name TEXT);
                CREATE INDEX name_lookup ON person_names(name);
                CREATE TABLE wiki (path TEXT PRIMARY KEY, title TEXT, body TEXT);
                CREATE VIRTUAL TABLE wiki_text USING fts5(path UNINDEXED, body, tokenize='unicode61');
            """)
            db.execute("INSERT INTO metadata VALUES (?)", (json.dumps(metadata),))
            for item in items:
                search_text = item.pop("search_text")
                db.execute("INSERT INTO items VALUES (?,?,?,?)", (item["id"], _key(item["handle"]), _key(item["type"]), json.dumps(item)))
                db.execute("INSERT INTO item_text VALUES (?,?)", (item["id"], search_text))
                for person in item["people"]:
                    db.execute("INSERT INTO people VALUES (?,?,?)", (item["id"], person["id"], person["role"]))
            for slug, person in persons.items():
                names = {slug, person["name"], *person.get("aliases", [])}
                db.executemany("INSERT INTO person_names VALUES (?,?)", [(slug, _key(name)) for name in names])
            for page in wiki_pages:
                db.execute("INSERT INTO wiki VALUES (?,?,?)", (page["path"], page["title"], page["body"]))
                db.execute("INSERT INTO wiki_text VALUES (?,?)", (page["path"], page["title"] + "\n" + page["body"]))
            db.commit()
        finally:
            db.close()
        # Detect changes while building. Keep the previous cache intact if inputs moved.
        if _current_manifest(root, inputs.manifest) != inputs.manifest:
            raise ValueError("Library inputs changed during indexing; stop other writers and rebuild")
        _cache(root)
        os.replace(temporary, cache)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return {"cache": CACHE, "indexed_at": metadata["indexed_at"], "coverage": coverage,
            "wiki_pages": len(wiki_pages), "warnings": inputs.warnings}


def _checked(root: Path) -> tuple[sqlite3.Connection, dict]:
    db = _connect(_cache(root))
    try:
        metadata = json.loads(db.execute("SELECT data FROM metadata").fetchone()[0])
        current = _current_manifest(root, metadata.get("manifest", {}))
        if metadata.get("version") != VERSION or metadata.get("manifest") != current:
            raise ValueError("Search index is stale; run indexx_search.py build --root <root>")
        return db, metadata
    except Exception:
        db.close()
        raise


def index_status(root: Path) -> dict:
    root = _root(root)
    db, metadata = _checked(root)
    db.close()
    return {"fresh": True, "cache": CACHE, "indexed_at": metadata["indexed_at"],
            "coverage": metadata["coverage"], "warnings": metadata["warnings"]}


def _fts(query: str) -> str:
    # Explicit quotes preserve a phrase; punctuation and operators are literal.
    chunks = re.findall(r'"([^"\n]+)"|(\S+)', query)
    terms = []
    for phrase, word in chunks:
        tokens = re.findall(r"[^\W_]+", phrase or word, re.UNICODE)
        if tokens:
            terms.append('"' + " ".join(tokens) + '"')
    return " AND ".join(terms)


def _excerpt(body: str, query: str) -> str:
    # This is display cleanup, not HTML rendering; preserve the actual words.
    body = re.sub(r"(?m)^\s{0,3}#{1,6}\s+", "", body)
    def wiki_label(match: re.Match) -> str:
        target, separator, label = match.group(1).partition("|")
        return label if separator else target.rsplit("/", 1)[-1].removesuffix(".md")
    body = re.sub(r"\[\[([^]\n]+)\]\]", wiki_label, body)
    body = re.sub(r"\[([^]\n]+)\]\((?:<[^>]*>|[^)\n]*)\)", r"\1", body)
    compact = re.sub(r"\s+", " ", body).strip()
    tokens = re.findall(r"[^\W_]+", query, re.UNICODE)
    position = next((compact.casefold().find(token.casefold()) for token in tokens if token.casefold() in compact.casefold()), 0)
    start = max(0, position - 70)
    return ("…" if start else "") + compact[start:start + 280] + ("…" if len(compact) > start + 280 else "")


def search(root: Path, query: str = "", person: Optional[str] = None, role: Optional[str] = None,
           uploader: Optional[str] = None, media_type: Optional[str] = None,
           limit: Optional[int] = 20, offset: int = 0) -> dict:
    root = _root(root)
    if not isinstance(query, str) or offset < 0 or (limit is not None and limit < 1):
        raise ValueError("Query must be text, offset nonnegative, and limit positive or None")
    if role is not None and role not in ROLES:
        raise ValueError("Role must be speaker, featured, or mentioned")
    expression = _fts(query)
    if query.strip() and not expression:
        raise ValueError("Text query needs at least one searchable word")
    db, metadata = _checked(root)
    try:
        clauses, parameters = [], []
        if expression:
            clauses.append("item_text MATCH ?")
            parameters.append(expression)
        if person is not None or role is not None:
            person_clauses = ["p.item_id = i.id"]
            if person is not None:
                matches = [row[0] for row in db.execute("SELECT DISTINCT person_id FROM person_names WHERE person_id = ?", (_key(person),))]
                if not matches:
                    matches = [row[0] for row in db.execute("SELECT DISTINCT person_id FROM person_names WHERE name = ?", (_key(person),))]
                if len(matches) > 1:
                    raise ValueError("Person name or alias is ambiguous; use a unique canonical person id")
                person_clauses.append("p.person_id = ?")
                parameters.append(matches[0] if matches else "")
            if role is not None:
                person_clauses.append("p.role = ?")
                parameters.append(role)
            clauses.append("EXISTS (SELECT 1 FROM people p WHERE " + " AND ".join(person_clauses) + ")")
        for column, value in (("handle", uploader), ("type", media_type)):
            if value is not None:
                clauses.append(f"i.{column} = ?")
                parameters.append(_key(value.lstrip("@") if column == "handle" else value))
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        source = "items i JOIN item_text ON item_text.id = i.id" if expression else "items i"
        ordering = "bm25(item_text), i.id COLLATE BINARY" if expression else "i.id COLLATE BINARY"
        total = db.execute("SELECT count(*) FROM " + source + where, parameters).fetchone()[0]
        page_args = parameters + [limit if limit is not None else -1, offset]
        records = db.execute("SELECT data FROM " + source + where + " ORDER BY " + ordering + " LIMIT ? OFFSET ?", page_args)
        results = []
        for record in records:
            item = json.loads(record[0])
            item["excerpt"] = _excerpt(item.pop("body"), query)
            results.append(item)
        wiki_results, wiki_total = [], 0
        if expression and all(value is None for value in (person, role, uploader, media_type)):
            wiki_from = " FROM wiki w JOIN wiki_text ON wiki_text.path = w.path WHERE wiki_text MATCH ?"
            wiki_total = db.execute("SELECT count(*)" + wiki_from, (expression,)).fetchone()[0]
            for page in db.execute("SELECT w.path,w.title,w.body" + wiki_from + " ORDER BY bm25(wiki_text),w.path LIMIT ? OFFSET ?", (expression, limit if limit is not None else -1, offset)):
                wiki_results.append({"path": page[0], "title": page[1], "excerpt": _excerpt(page[2], query)})
        return {"results": results, "total": total, "coverage": metadata["coverage"], "indexed_at": metadata["indexed_at"],
                "wiki_results": wiki_results, "wiki_total": wiki_total, "warnings": metadata["warnings"]}
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    for command in ("build", "query", "status"):
        subparser = subcommands.add_parser(command)
        subparser.add_argument("--root", required=True)
        if command == "query":
            subparser.add_argument("--text", default="")
            subparser.add_argument("--person")
            subparser.add_argument("--role", choices=sorted(ROLES))
            subparser.add_argument("--uploader")
            subparser.add_argument("--type", dest="media_type")
            subparser.add_argument("--limit", type=int, default=20)
            subparser.add_argument("--offset", type=int, default=0)
            subparser.add_argument("--all", action="store_true", help="Return every matching catalog item")
    args = parser.parse_args()
    try:
        root = Path(args.root)
        if args.command == "build":
            result = build_index(root)
        elif args.command == "status":
            result = index_status(root)
        else:
            result = search(root, args.text, args.person, args.role, args.uploader, args.media_type,
                            None if args.all else args.limit, args.offset)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(f"Search stopped: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
