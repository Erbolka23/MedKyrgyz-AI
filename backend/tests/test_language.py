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


from app.services.language_service import detect_language_or_none  # noqa: E402


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Short Russian messages must not fall back to Kyrgyz
        ("Горло першит", "ru"),
        ("Тошнит второй день", "ru"),
        ("Кашляю неделю", "ru"),
        ("Сыпь чешется", "ru"),
        # Kyrgyz typed without special letters
        ("Кокурогум катуу ооруп жатат", "ky"),
        ("Журогум ооруп жатат", "ky"),
        ("Бугун башым ооруйт", "ky"),
        ("Дем алуу кыйын", "ky"),
    ],
)
def test_detect_short_and_keyboard_variants(text: str, expected: str) -> None:
    assert detect_language_or_none(text) == expected


@pytest.mark.parametrize("text", ["123", "???", "ok", "Парацетамол"])
def test_undetermined_language_returns_none(text: str) -> None:
    assert detect_language_or_none(text) is None
