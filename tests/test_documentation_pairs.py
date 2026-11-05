"""Каждому основному публичному Markdown соответствует связанный перевод."""

import unittest
from pathlib import Path


class DocumentationPairsTests(unittest.TestCase):
    def test_all_public_root_and_docs_markdown_has_reciprocal_translation(self):
        root = Path(__file__).resolve().parents[1]
        source_paths = list(root.glob("*.md")) + list((root / "docs").glob("*.md"))
        originals = [p for p in source_paths if not p.name.endswith(".en.md")]
        self.assertTrue(originals)
        for source in originals:
            english = source.with_name(source.stem + ".en.md")
            with self.subTest(document=str(source.relative_to(root))):
                self.assertTrue(english.is_file(), "Нет перевода на английский")
                self.assertIn(
                    "(" + english.name + ")", source.read_text(encoding="utf-8")
                )
                self.assertIn(
                    "(" + source.name + ")", english.read_text(encoding="utf-8")
                )


if __name__ == "__main__":
    unittest.main()
