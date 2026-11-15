"""Основные документы обязаны иметь взаимные ссылки на переводы."""
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = [
    path for path in (list(ROOT.glob("*.md")) + list((ROOT / "docs").glob("*.md")))
    if not path.name.endswith(".en.md")
]


def test_documentation_corpus_is_not_empty():
    assert DOCUMENTS


@pytest.mark.parametrize("source", DOCUMENTS, ids=lambda p: str(p.relative_to(ROOT)))
def test_public_document_has_reciprocal_translation(source: Path):
    english = source.with_name(source.stem + ".en.md")
    assert english.is_file(), f"Нет перевода на английский: {source.name}"
    assert f"({english.name})" in source.read_text(encoding="utf-8")
    assert f"({source.name})" in english.read_text(encoding="utf-8")
