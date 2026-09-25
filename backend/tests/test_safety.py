from __future__ import annotations

import pytest

from app.core.prompts import MEDICATION_REFUSALS
from app.services.safety_service import AnswerGuard, EmergencyDetector


@pytest.mark.parametrize(
    "message",
    [
        "Дем ала албай жатам",
        "Атам эсин жоготту",
        "У меня сильная боль в груди",
        "Ребенок задыхается",
        "Не хочу жить",
    ],
)
def test_emergency_detected(message: str) -> None:
    assert EmergencyDetector().check(message).is_emergency


@pytest.mark.parametrize("message", ["Башым ооруп жатат", "Болит горло второй день"])
def test_non_emergency(message: str) -> None:
    assert not EmergencyDetector().check(message).is_emergency


def test_guard_blocks_dosage() -> None:
    answer = "Примите ибупрофен 400 мг три раза в день."
    assert AnswerGuard().sanitise(answer, "ru") == MEDICATION_REFUSALS["ru"]


def test_guard_passes_safe_answer() -> None:
    answer = "Пейте больше воды и отдыхайте. Если станет хуже — обратитесь к врачу."
    assert AnswerGuard().sanitise(answer, "ru") == answer
