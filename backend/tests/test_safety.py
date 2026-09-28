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


# ---------------------------------------------------------------------------
# EmergencyDetector — extended scenarios
# ---------------------------------------------------------------------------

from app.core.prompts import DIAGNOSIS_REFUSALS  # noqa: E402


@pytest.mark.parametrize(
    ("message", "category"),
    [
        # Russian — required scenarios
        ("У меня сильная боль в груди", "chest_pain"),
        ("Болит в груди и трудно дышать", "chest_pain"),
        ("Потеря сознания у мамы", "unconsciousness"),
        ("Сильное кровотечение из раны", "bleeding"),
        # Russian — other categories
        ("Давит в груди уже полчаса", "chest_pain"),
        ("Папа потерял сознание", "unconsciousness"),
        ("Перекосило лицо, речь невнятная", "stroke"),
        ("Кровь не останавливается", "bleeding"),
        ("После укуса пчелы отекло горло", "allergy"),
        ("У ребенка начались судороги", "seizure"),
        ("Внезапно началась сильная головная боль", "severe_pain"),
        ("Невыносимая боль в животе", "severe_pain"),
        ("Не могу дышать", "breathing"),
        ("Выпил много таблеток снотворного", "poisoning"),
        # Kyrgyz — required scenarios (with and without special letters)
        ("Көкүрөгүм катуу ооруп жатат", "chest_pain"),
        ("Кокурогум катуу ооруп жатат", "chest_pain"),
        ("Дем алуу кыйын болуп жатат", "breathing"),
        ("Жүрөгүм ооруп жатат", "chest_pain"),
        ("Журогум ооруп жатат", "chest_pain"),
        ("Тошум ооруп дем алуу кыйын", "chest_pain"),
        # Kyrgyz — other categories
        ("Төшүм кысып ооруп жатат", "chest_pain"),
        ("Атам эсинен танды", "unconsciousness"),
        ("Бетим кыйшайып калды", "stroke"),
        ("Кан токтобой жатат", "bleeding"),
        ("Баламды талма кармады", "seizure"),
        ("Башым капыстан катуу ооруп калды", "severe_pain"),
        ("Аары чагып, тамагым шишип кетти", "allergy"),
        ("Тамагым шишип, дем ала албай жатам", "breathing"),
        ("Жашагым келбейт", "self_harm"),
    ],
)
def test_emergency_categories(message: str, category: str) -> None:
    result = EmergencyDetector().check(message)
    assert result.is_emergency, message
    assert result.category == category, (message, result.category)


@pytest.mark.parametrize(
    "message",
    [
        # Russian — ordinary questions
        "Температура 38.5, болит голова",
        "Немного болит грудь при кашле",
        "Судорога в ноге ночью",
        "Трудно дышать носом из-за насморка",
        "Какое давление считается нормальным?",
        "У грудного ребенка насморк",
        "Сильно кашляю третий день",
        # Kyrgyz — ordinary questions
        "Башым ооруп жатат",
        "Башым катуу ооруп жатат",
        "Жүрөгүм айланып, ичим ооруп жатат",
        "Журогум айланып жатат",
        "Кан басымым кандай болушу керек?",
        "Тамагым ооруп жатат",
        "Тамагым шишип ооруп жатат",
        "Мурдум менен дем алуу кыйын",
    ],
)
def test_ordinary_messages_are_not_emergency(message: str) -> None:
    result = EmergencyDetector().check(message)
    assert not result.is_emergency, (message, result.matched)


# ---------------------------------------------------------------------------
# AnswerGuard — dosage, prescription, diagnosis
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        "Температура 38.5°C считается повышенной. Пейте больше жидкости.",
        "Выпейте 300 мл тёплой воды и отдохните.",
        "Пейте воду 3 раза в день небольшими порциями.",
        "Такие симптомы бывают при гриппе или простуде, но точную причину определит только врач.",
        "Мигрень — это вид головной боли. Обратитесь к неврологу.",
        "Я не врач, но могу рассказать общую информацию.",
        "Лекарство и дозу может подобрать только врач.",
        "Ысыгыңыз 38°C болсо, көп суюктук ичиңиз жана дарыгерге кайрылыңыз.",
        "Мындай белгилер гастритте да болушу мүмкүн, бирок так себебин дарыгер аныктайт.",
    ],
)
def test_guard_allows_educational_answers(answer: str) -> None:
    assert AnswerGuard().review(answer).is_safe, answer


@pytest.mark.parametrize(
    ("answer", "reason"),
    [
        ("Примите 500 мг парацетамола.", "dosage"),
        ("Можно выпить 2 таблетки анальгина.", "dosage"),
        ("Давайте сироп по 5 мл.", "dosage"),
        ("Принимайте лекарство 3 раза в день.", "dosage"),
        ("Бир таблетка ичиңиз.", "dosage"),
        ("Примите ибупрофен.", "prescription"),
        ("Ибупрофен ичиңиз.", "prescription"),
        ("У вас грипп.", "diagnosis"),
        ("У вас точно гастрит.", "diagnosis"),
        ("Сизде гастрит бар.", "diagnosis"),
        ("Я ваш врач, и я осмотрел результаты.", "diagnosis"),
    ],
)
def test_guard_blocks_unsafe_answers(answer: str, reason: str) -> None:
    result = AnswerGuard().review(answer)
    assert not result.is_safe, answer
    assert result.reason == reason, (answer, result.reason)


def test_guard_replaces_diagnosis_with_refusal() -> None:
    assert AnswerGuard().sanitise("У вас пневмония.", "ru") == DIAGNOSIS_REFUSALS["ru"]
    assert AnswerGuard().sanitise("Сизде ангина бар.", "ky") == DIAGNOSIS_REFUSALS["ky"]
