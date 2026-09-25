"""
Safety layer.

Two independent guards surround the LLM:

  * EmergencyDetector (input guard) — finds life-threatening symptoms in the
    user's message. When triggered, the backend answers with a fixed,
    human-reviewed emergency message and does NOT call the LLM at all, so the
    warning is instant and cannot be altered by the model.

  * AnswerGuard (output guard) — checks the LLM answer for concrete medication
    dosages. The system prompt already forbids prescribing; this is the
    second line of defence in case the model ignores it.

Keyword lists are deliberately conservative: a false alarm is far cheaper
than a missed emergency.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.core.prompts import EMERGENCY_MESSAGES, MEDICATION_REFUSALS

# Phrase fragments (already lower-cased, "ё" normalised to "е").
EMERGENCY_PATTERNS_KY: tuple[str, ...] = (
    "дем ала албай", "демим кысыл", "демим жетпей", "тумчугуп",
    "көкүрөгүм катуу", "төшүм катуу", "жүрөгүм катуу ооруп", "жүрөгүм кысып",
    "эсин жоготту", "эси ооп", "эсинен тан", "эс-учун жогот",
    "кан токтобой", "кан кусуп", "кан аралаш кус",
    "талма", "бетим кыйшай", "бети кыйшай", "колум сезбей", "шал болуп",
    "өзүмдү өлтүр", "жашагым келбей", "өлгүм келет",
    "инсульт", "инфаркт",
)

EMERGENCY_PATTERNS_RU: tuple[str, ...] = (
    "не могу дышать", "трудно дышать", "задыха", "нечем дышать",
    "боль в груди", "болит грудь", "давит в груди", "жжет в груди",
    "потерял сознание", "потеряла сознание", "потеря сознания", "без сознания", "обморок",
    "сильное кровотечение", "кровь не останавливается", "рвота с кровью", "рвет кровью",
    "судорог", "инсульт", "инфаркт", "онемела", "онемел", "перекосило",
    "покончить с собой", "суицид", "не хочу жить", "убить себя",
    "отек горла", "отекло горло", "анафилак",
)

# e.g. "500 мг", "2 таблетки", "10 ml", "по 1 капсуле"
_DOSAGE_RE = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:мг|mg|мкг|мл|ml|г\b|гр\b|таблет|капсул|тамчы|капл|ампул)",
    re.IGNORECASE,
)


def _normalise(text: str) -> str:
    text = text.lower().replace("ё", "е")
    return re.sub(r"\s+", " ", text)


@dataclass(frozen=True)
class EmergencyCheck:
    is_emergency: bool
    matched: str | None = None


class EmergencyDetector:
    """Detects emergency symptoms regardless of the message language."""

    def __init__(self, patterns: tuple[str, ...] = EMERGENCY_PATTERNS_KY + EMERGENCY_PATTERNS_RU) -> None:
        self._patterns = tuple(_normalise(p) for p in patterns)

    def check(self, message: str) -> EmergencyCheck:
        normalised = _normalise(message)
        for pattern in self._patterns:
            if pattern in normalised:
                return EmergencyCheck(is_emergency=True, matched=pattern)
        return EmergencyCheck(is_emergency=False)

    @staticmethod
    def emergency_message(language: str) -> str:
        return EMERGENCY_MESSAGES[language]


class AnswerGuard:
    """Post-processes LLM output before it reaches the user."""

    @staticmethod
    def contains_dosage(answer: str) -> bool:
        return bool(_DOSAGE_RE.search(answer))

    def sanitise(self, answer: str, language: str) -> str:
        answer = answer.strip()
        if not answer:
            return MEDICATION_REFUSALS[language]
        if self.contains_dosage(answer):
            return MEDICATION_REFUSALS[language]
        return answer
