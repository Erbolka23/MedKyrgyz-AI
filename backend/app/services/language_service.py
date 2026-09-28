"""
Lightweight Kyrgyz / Russian language detection.

Used only when the client sends `language: "auto"`. When the user explicitly
selects "ky" or "ru" (the frontend always does), that choice always wins and
this module is not called.

Both languages use Cyrillic, so detection combines several signals:
  1. Kyrgyz-only letters (ң, ө, ү)                       -> certain Kyrgyz;
  2. frequent Kyrgyz / Russian words (Kyrgyz words are also matched in
     their "Russian keyboard" spelling: көкүрөк -> кокурок);
  3. typical word endings (Russian -ит, -ют, -ость...; Kyrgyz -жатат, -ганда...);
  4. Kyrgyz double vowels (оо, уу, аа, ыы, ээ) and Russian-only letters (ь, щ, ъ).

If the signal is too weak or balanced, `detect_language_or_none` returns None
instead of guessing, and the caller decides the fallback.
"""

from __future__ import annotations

import re

KYRGYZ_LETTERS = frozenset("ңөү")
RUSSIAN_ONLY_LETTERS = frozenset("ьщъ")

_KY_FOLD = str.maketrans({"ө": "о", "ү": "у", "ң": "н", "ё": "е"})

_KYRGYZ_WORDS_BASE = frozenset({
    "жана", "менен", "эмне", "эмнеге", "кандай", "канча", "качан", "кайда", "барбы", "жокпу",
    "менин", "сенин", "сиздин", "мен", "сен", "биз", "алар", "бул", "ошол", "керек", "болот",
    "жатат", "жатам", "жатабы", "ооруп", "оорусу", "оору", "ооруйт", "башым", "ичим", "тишим",
    "бутум", "колум", "белим", "дарыгер", "дары", "бала", "балам", "ысыгым", "ысык", "жөтөл",
    "салам", "рахмат", "эмес", "дагы", "абдан", "бир", "күн", "бери", "кийин", "мурун", "кечээ",
    "бүгүн", "катуу", "көкүрөгүм", "жүрөгүм", "төшүм", "дем", "алуу", "кыйын", "болуп", "калды",
    "кылсам", "кылыш", "жакшы", "жаман", "бар", "жок", "көп", "аз", "эки", "үч",
})
# Also accept the spelling without Kyrgyz-specific letters (Russian keyboard).
KYRGYZ_WORDS = _KYRGYZ_WORDS_BASE | frozenset(w.translate(_KY_FOLD) for w in _KYRGYZ_WORDS_BASE)

RUSSIAN_WORDS = frozenset({
    "и", "в", "не", "на", "что", "как", "это", "у", "меня", "мне", "есть", "очень", "болит",
    "болят", "боль", "голова", "голову", "горло", "живот", "спина", "сердце", "грудь", "груди",
    "температура", "температуры", "кашель", "кашляю", "насморк", "тошнит", "рвота", "понос",
    "сыпь", "чешется", "першит", "давление", "врач", "врачу", "врача", "лекарство", "таблетки",
    "можно", "нужно", "надо", "почему", "когда", "сколько", "где", "делать", "уже", "дня", "день",
    "неделю", "вчера", "сегодня", "здравствуйте", "спасибо", "ребенок", "ребенка", "после",
    "сильно", "сильная", "немного", "я", "он", "она", "мой", "моя", "у", "с", "по", "от", "при",
    "или", "но", "если", "ли",
})

KYRGYZ_SUFFIXES = (
    "жатат", "жатам", "жатабы", "жатасыз", "ымын", "ганда", "генде", "гонго", "ымда",
    "бейт", "байт", "дыбы", "бызбы", "сызбы",
)
RUSSIAN_SUFFIXES = (
    "ться", "тся", "ешь", "ишь", "ость", "ение", "ание", "ого", "его", "ому", "ему",
    "ый", "ий", "ют", "ят", "ит",
)

_KYRGYZ_DOUBLE_VOWELS = re.compile(r"(?:оо|уу|аа|ыы|ээ)")
_WORD_RE = re.compile(r"[а-яёңөү]+")

# The winner must reach this score AND beat the other language.
MIN_SCORE = 1.0


def _score(text: str) -> tuple[float, float]:
    ky_score = 0.0
    ru_score = 0.0
    for token in _WORD_RE.findall(text):
        folded = token.translate(_KY_FOLD)

        if token in KYRGYZ_WORDS or folded in KYRGYZ_WORDS:
            ky_score += 1
        elif folded.endswith(KYRGYZ_SUFFIXES):
            ky_score += 0.5
        elif _KYRGYZ_DOUBLE_VOWELS.search(folded):
            ky_score += 0.5

        if token in RUSSIAN_WORDS or folded in RUSSIAN_WORDS:
            ru_score += 1
        elif any(letter in RUSSIAN_ONLY_LETTERS for letter in token):
            ru_score += 0.5
        elif folded.endswith(RUSSIAN_SUFFIXES):
            ru_score += 0.5
    return ky_score, ru_score


def detect_language_or_none(text: str) -> str | None:
    """Return "ky" or "ru", or None when the language cannot be determined reliably."""
    lowered = text.lower()
    if any(letter in KYRGYZ_LETTERS for letter in lowered):
        return "ky"

    ky_score, ru_score = _score(lowered.replace("ё", "е"))
    if ky_score >= MIN_SCORE and ky_score > ru_score:
        return "ky"
    if ru_score >= MIN_SCORE and ru_score > ky_score:
        return "ru"
    return None


def detect_language(text: str, default: str = "ky") -> str:
    """Return "ky" or "ru". Falls back to `default` when the signal is weak."""
    return detect_language_or_none(text) or default
