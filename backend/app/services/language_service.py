"""
Lightweight Kyrgyz / Russian language detection.

Both languages use Cyrillic, so detection relies on:
  1. Kyrgyz-only letters (ң, ө, ү) — a strong signal;
  2. frequent Kyrgyz and Russian words and word endings — a scoring signal.

This is intentionally dependency-free and fast. It can later be replaced by
a trained classifier without changing the `detect_language` signature.
"""

from __future__ import annotations

import re

KYRGYZ_LETTERS = frozenset("ңөү")

KYRGYZ_WORDS = frozenset({
    "жана", "менен", "эмне", "эмнеге", "кандай", "канча", "качан", "кайда", "барбы", "жокпу",
    "менин", "сенин", "сиздин", "мен", "сен", "биз", "алар", "бул", "ошол", "керек", "болот",
    "жатат", "жатам", "жатабы", "ооруп", "оорусу", "оору", "башым", "ичим", "тишим", "бутум",
    "колум", "белим", "дарыгер", "дары", "бала", "балам", "ысыгым", "жөтөл", "салам", "рахмат",
    "эмес", "дагы", "абдан", "бир", "күн", "бери", "кийин", "мурун", "кечээ", "бүгүн",
})

RUSSIAN_WORDS = frozenset({
    "и", "в", "не", "на", "что", "как", "это", "у", "меня", "мне", "есть", "очень", "болит",
    "болят", "голова", "живот", "температура", "кашель", "врач", "врачу", "можно", "нужно",
    "почему", "когда", "сколько", "где", "делать", "уже", "дня", "день", "здравствуйте",
    "спасибо", "ребенок", "ребенка", "после", "сильно", "сильная", "давление", "я", "он", "она",
})

KYRGYZ_SUFFIXES = ("жатат", "жатам", "ымын", "ганда", "генде", "ымда", "бейт", "байт", "дыбы", "бызбы")
RUSSIAN_SUFFIXES = ("ться", "тся", "ого", "его", "ый", "ий", "ая", "ешь", "ишь")

_WORD_RE = re.compile(r"[а-яёңөү]+", re.IGNORECASE)


def _tokens(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower().replace("ё", "е"))


def detect_language(text: str, default: str = "ky") -> str:
    """Return "ky" or "ru". Falls back to `default` when the signal is weak."""
    lowered = text.lower()
    if any(letter in KYRGYZ_LETTERS for letter in lowered):
        return "ky"

    tokens = _tokens(lowered)
    if not tokens:
        return default

    ky_score = 0.0
    ru_score = 0.0
    for token in tokens:
        if token in KYRGYZ_WORDS:
            ky_score += 1
        elif token.endswith(KYRGYZ_SUFFIXES):
            ky_score += 0.5
        if token in RUSSIAN_WORDS:
            ru_score += 1
        elif token.endswith(RUSSIAN_SUFFIXES):
            ru_score += 0.5

    if ky_score > ru_score:
        return "ky"
    if ru_score > ky_score:
        return "ru"
    return default
