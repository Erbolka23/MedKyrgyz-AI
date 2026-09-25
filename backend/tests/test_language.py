from __future__ import annotations

import pytest

from app.services.language_service import detect_language


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Башым ооруп жатат", "ky"),
        ("Менин балам үч күндөн бери жөтөлүп жатат", "ky"),
        ("Ичим ооруйт, эмне кылсам болот?", "ky"),
        ("У меня болит голова", "ru"),
        ("Что делать, если температура держится три дня?", "ru"),
    ],
)
def test_detect_language(text: str, expected: str) -> None:
    assert detect_language(text) == expected


def test_detect_language_falls_back_to_default() -> None:
    assert detect_language("123 ???", default="ru") == "ru"
