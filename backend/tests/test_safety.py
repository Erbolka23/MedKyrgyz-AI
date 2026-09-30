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


# ---------------------------------------------------------------------------
# Bug C1 — clarifying questions must not be treated as diagnoses
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        # RU
        "У вас есть диабет или астма?",
        "Есть ли у вас аллергия?",
        "У вас раньше было такое?",
        "Принимали ли вы какие-либо лекарства?",
        "Имеете ли вы гастрит или язву",
        "Есть ли у вас диабет",
        "Чтобы лучше понять ситуацию: у вас есть астма? Как давно болит голова?",
        # KY
        "Сизде диабет барбы?",
        "Аллергияңыз барбы?",
        "Мурда мындай болгонбу?",
        "Дары ичтиңиз беле?",
        "Сизде гастрит бар бекен",
        "Сизде диабет барбы",
        "Мурда гастрит менен ооругансызбы?",
    ],
)
def test_guard_allows_clarifying_questions(answer: str) -> None:
    assert not AnswerGuard().contains_diagnosis(answer), answer
    assert AnswerGuard().review(answer).is_safe, answer


@pytest.mark.parametrize(
    "answer",
    [
        "У вас грипп",
        "Сизде гастрит бар",
        "У вас есть диабет.",
        "У вас точно гастрит. Есть ли у вас температура?",
        "Сизде гастрит бар. Аллергияңыз барбы?",
        "У вас грипп, понятно?",
        "У вас грипп, но есть ли осложнения?",
        "Сизде гастрит бар, туурабы?",
    ],
)
def test_guard_still_blocks_diagnosis_statements(answer: str) -> None:
    result = AnswerGuard().review(answer)
    assert not result.is_safe, answer
    assert result.reason == "diagnosis", (answer, result.reason)


# ---------------------------------------------------------------------------
# Bug C2 — suicidal intent and fainting / collapse (RU + KY)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "category"),
    [
        # Suicidal intent — RU
        ("Хочу умереть", "self_harm"),
        ("Я не хочу жить", "self_harm"),
        ("Жить не хочу больше", "self_harm"),
        ("Мне так плохо, хочется умереть", "self_harm"),
        ("Не хочется жить", "self_harm"),
        # Suicidal intent — KY
        ("Өлгүм келет", "self_harm"),
        ("Олгум келип жатат", "self_harm"),
        ("Жашагым келбейт", "self_harm"),
        ("Жашоонун мааниси жок", "self_harm"),
        # Fainting / loss of consciousness — KY
        ("Талып калды", "unconsciousness"),
        ("Балам талып калды", "unconsciousness"),
        ("Апам талып жыгылды", "unconsciousness"),
        ("Жыгылып калды", "unconsciousness"),
        ("Атам жыгылып калды, жооп бербей жатат", "unconsciousness"),
        ("Жыгылып турбай жатат", "unconsciousness"),
        ("Эсинен танып калды", "unconsciousness"),
        ("Эстен танды", "unconsciousness"),
        # Fainting / loss of consciousness — RU
        ("Сознание потерял на улице", "unconsciousness"),
        ("Упал и не встает", "unconsciousness"),
        ("Упала в обморок", "unconsciousness"),
    ],
)
def test_c2_emergency_detected(message: str, category: str) -> None:
    result = EmergencyDetector().check(message)
    assert result.is_emergency, message
    assert result.category == category, (message, result.category)


@pytest.mark.parametrize(
    "message",
    [
        # Figurative / everyday RU
        "Чуть не умерла со смеху, хочу умереть от смеха",
        "Я хочу жить здоровой жизнью",
        "Устал, хочу спать",
        "Упал с велосипеда, болит колено",
        # Numb or tired limbs are not fainting — KY
        "Колум талып калды",
        "Бутум талып калды, ийне сайгандай",
        "Белим талып калды",
        # The user describing their own fall is conscious
        "Кечээ жыгылып калдым, тизем ооруйт",
        # Everyday KY
        "Эсимде жок, качан башталганы",
        "Жашоо образын кантип өзгөртсө болот?",
        "Чарчап калдым",
    ],
)
def test_c2_ordinary_messages_are_not_emergency(message: str) -> None:
    result = EmergencyDetector().check(message)
    assert not result.is_emergency, (message, result.matched)


# ---------------------------------------------------------------------------
# Prescription detection — direct medication advice (RU + KY)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "answer",
    [
        # RU — required examples
        "Возьмите ибупрофен.",
        "Можно выпить Нурофен.",
        "Нурофен поможет, купите его.",
        # RU — other commands and recommendations
        "Примите парацетамол, если болит.",
        "Купите в аптеке нурофен.",
        "Вам поможет ибупрофен.",
        "Ибупрофен вам поможет.",
        "Попробуйте цитрамон.",
        "Можете сегодня принять аспирин.",
        "Вам стоит выпить анальгин.",
        "Рекомендую ибупрофен при такой боли.",
        "При температуре парацетамол поможет.",
        # KY
        "Ибупрофен ичиңиз.",
        "Парацетамол ичип көрүңүз.",
        "Нурофен ичсеңиз болот.",
        "Дарыканадан парацетамол сатып алыңыз.",
        "Ибупрофен сизге жардам берет.",
        "Цитрамонду колдонуңуз.",
        "Нурофен жакшы, аны сатып алыңыз.",
        "Аспирин сунуштайм.",
    ],
)
def test_guard_blocks_medication_advice(answer: str) -> None:
    result = AnswerGuard().review(answer)
    assert not result.is_safe, answer
    assert result.reason == "prescription", (answer, result.reason)


@pytest.mark.parametrize(
    "answer",
    [
        # RU — required examples
        "Ибупрофен относится к группе НПВС.",
        "Нурофен содержит ибупрофен.",
        # RU — education and safety advice
        "Парацетамол и ибупрофен снижают температуру, но подобрать лекарство должен врач.",
        "Ибупрофен может помочь при боли, но у него есть противопоказания.",
        "Не принимайте ибупрофен без консультации врача.",
        "Антибиотики не помогут при вирусной инфекции.",
        "Ибупрофен не поможет при вирусе.",
        "Пейте больше воды, а про парацетамол спросите у врача.",
        "Купите термометр и измеряйте температуру.",
        "Возьмите с собой к врачу список всех лекарств.",
        "Аспирин нельзя давать детям.",
        # KY — education and safety advice
        "Ибупрофен ооруну басат, бирок аны дарыгер гана жазып берет.",
        "Парацетамол ысыкты түшүрөт.",
        "Дарыгердин кеңешисиз антибиотик ичпеңиз.",
        "Көп суу ичиңиз жана эс алыңыз.",
    ],
)
def test_guard_allows_medication_education(answer: str) -> None:
    result = AnswerGuard().review(answer)
    assert result.is_safe, (answer, result.reason)


def test_guard_prescription_does_not_mask_dosage_or_diagnosis() -> None:
    guard = AnswerGuard()
    assert guard.review("Примите 400 мг ибупрофена.").reason == "dosage"
    assert guard.review("Нурофен ичиңиз, 2 таблетка.").reason == "dosage"
    assert guard.review("У вас грипп.").reason == "diagnosis"
    assert guard.review("Сизде гастрит бар.").reason == "diagnosis"


# ---------------------------------------------------------------------------
# Headache false positives — heart + pain words elsewhere in the message
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "У меня болит голова уже второй день",
        "Башым эки күндөн бери ооруп жатат",
        "Сильно болит голова",
        "Острая боль в голове второй день",
        "Головная боль с утра, давит в висках",
        # "болит"/"давит" belong to the head, not to the heart
        "Болит голова и сердце колотится",
        "Сердце колотится, и болит голова",
        "Давит в висках, сердце стучит",
        "Башым ооруп, жүрөгүм кагып жатат",
        "Башым ооруп жатат, жүрөгүм тез согуп жатат",
    ],
)
def test_headache_is_not_emergency(message: str) -> None:
    result = EmergencyDetector().check(message)
    assert not result.is_emergency, (message, result.matched)


@pytest.mark.parametrize(
    "message",
    [
        "Болит сердце",
        "Сердце сильно болит",
        "Боль в сердце",
        "Колет в области сердца",
        "Давит на сердце",
        "Сердце давит",
        "Жүрөгүм ооруп жатат",
        "Жүрөгүм катуу ооруп жатат",
        "Жүрөгүм кысып жатат",
        "Болит голова и сильно болит сердце",
    ],
)
def test_heart_pain_is_still_emergency(message: str) -> None:
    result = EmergencyDetector().check(message)
    assert result.is_emergency, message
    assert result.category == "chest_pain", (message, result.category)
