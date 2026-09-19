"""Person identity metadata stays explicit, source-linked, and optional."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from indexx_status import Invalid, person_annotations, person_page


class PeopleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.path = self.root / "wiki/entities/people/example-person.md"
        self.path.parent.mkdir(parents=True)
        self.page = {"id": "example-person", "name": "Example Person", "aliases": ["E. Person"]}
        self.annotation = {"id": "example-person", "name": "Example Person", "role": "speaker",
                           "evidence": "The archived caption credits Example Person as speaker."}
        self.write_page()

    def write_page(self, body="The caption credits this speaker. [[sources/instagram/Example123]]"):
        self.path.write_text("---\n" + "\n".join(f"{k}: {json.dumps(v)}" for k, v in self.page.items())
                             + "\n---\n# Example Person\n\n" + body)

    def source(self, people=None, reviewed=True):
        return {"id": "Example123", "people": people if people is not None else [self.annotation],
                "people_reviewed": reviewed}

    def test_legacy_and_explicit_no_people_have_different_review_state(self):
        self.assertEqual(person_annotations({}, self.root), [])
        self.assertEqual(person_annotations(self.source([]), self.root), [])
        with self.assertRaisesRegex(Invalid, "explicit people list"):
            person_annotations({"people_reviewed": True}, self.root)
        with self.assertRaisesRegex(Invalid, "boolean"):
            person_annotations({"people_reviewed": "yes"}, self.root)

    def test_canonical_identity_aliases_and_source_link(self):
        self.assertEqual(person_page(self.root, "example-person")["aliases"], ["E. Person"])
        self.assertEqual(person_annotations(self.source(), self.root), [self.annotation])
        self.write_page("See [clip](../../sources/instagram/Example123.md).")
        self.assertEqual(person_annotations(self.source(reviewed=False), self.root), [self.annotation])

    def test_all_roles_valid_but_duplicates_rejected(self):
        people = [dict(self.annotation, role=role) for role in ("speaker", "featured", "mentioned")]
        self.assertEqual(len(person_annotations(self.source(people), self.root)), 3)
        with self.assertRaisesRegex(Invalid, "duplicate"):
            person_annotations(self.source(people + people[:1]), self.root)
        with self.assertRaisesRegex(Invalid, "role"):
            person_annotations(self.source([dict(self.annotation, role="uploader")]), self.root)

    def test_empty_evidence_and_identity_mismatch_rejected(self):
        with self.assertRaisesRegex(Invalid, "nonempty"):
            person_annotations(self.source([dict(self.annotation, evidence=" ")]), self.root)
        with self.assertRaisesRegex(Invalid, "canonical"):
            person_annotations(self.source([dict(self.annotation, name="Someone Else")]), self.root)
        self.write_page("See [[sources/instagram/Example1234]].")
        with self.assertRaisesRegex(Invalid, "must link source"):
            person_annotations(self.source(), self.root)
        for body in ("The literal path sources/instagram/Example123 appears here.",
                     "See [clip](https://example.org/sources/instagram/Example123.md)."):
            self.write_page(body)
            with self.assertRaisesRegex(Invalid, "must link source"):
                person_annotations(self.source(), self.root)

    def test_bad_aliases_heading_only_and_missing_pages_rejected(self):
        self.page["aliases"] = ["E. Person", "e. person"]
        self.write_page()
        with self.assertRaisesRegex(Invalid, "distinct"):
            person_page(self.root, "example-person")
        self.page["aliases"] = []
        self.write_page("")
        with self.assertRaisesRegex(Invalid, "cited body"):
            person_page(self.root, "example-person")
        self.path.unlink()
        with self.assertRaisesRegex(Invalid, "missing"):
            person_annotations(self.source(), self.root)

    def test_person_paths_cannot_escape_library(self):
        for slug in ("../../outside", "../person", "/tmp/person"):
            with self.subTest(slug=slug), self.assertRaises(Invalid):
                person_page(self.root, slug)
        with tempfile.TemporaryDirectory() as other:
            outside = Path(other) / "person.md"
            outside.write_text(self.path.read_text())
            self.path.unlink()
            self.path.symlink_to(outside)
            with self.assertRaisesRegex(Invalid, "escapes"):
                person_annotations(self.source(), self.root)


if __name__ == "__main__":
    unittest.main()
