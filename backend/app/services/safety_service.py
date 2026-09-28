"""
Safety layer.

Two independent guards surround the LLM:

  * EmergencyDetector (input guard) — finds life-threatening symptoms in the
    user's message. When triggered, the backend answers with a fixed,
    human-reviewed emergency message and does NOT call the LLM at all, so the
    warning is instant and cannot be altered by the model.

  * AnswerGuard (output guard) — checks the LLM answer for concrete dosages,
    direct prescriptions and categorical diagnoses. The system prompt already
    forbids them; this is the second line of defence if the model ignores it.

How emergency detection works
-----------------------------
1. The text is normalised: lower case, "ё"→"е", and the Kyrgyz letters
   "ө"→"о", "ү"→"у", "ң"→"н" (many people type Kyrgyz on a Russian keyboard),
   punctuation removed. All patterns below are written for normalised text.
2. Known harmless phrases are removed first (e.g. "жүрөгүм айланып" = nausea,
   "судорога в ноге" = muscle cramp).
3. Each category is matched either by a single strong phrase, or by a
   combination of concepts that must ALL be present
   (e.g. chest + severe pain, or heart + pain).

Plain words such as "боль" or "грудь" alone never trigger an emergency.
The detector stays keyword-based on purpose: it is transparent, fast and easy
to review, which matters more for a safety net than cleverness.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.core.logging import get_logger
from app.core.prompts import DIAGNOSIS_REFUSALS, EMERGENCY_MESSAGES, MEDICATION_REFUSALS

logger = get_logger(__name__)

# ============================================================================
# Normalisation
# ============================================================================

_CHAR_MAP = str.maketrans({"ё": "е", "ө": "о", "ү": "у", "ң": "н"})


def normalise_text(text: str, keep_punctuation: bool = False) -> str:
    """Lower-case, fold Kyrgyz-specific letters and (optionally) drop punctuation."""
    text = text.lower().translate(_CHAR_MAP)
    if not keep_punctuation:
        text = re.sub(r"[^\w\s]|_", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# ============================================================================
# Emergency detection — building blocks (for NORMALISED text)
# ============================================================================

_GAP = r"(?:\w+\s+)"  # one arbitrary word between two key words

CHEST = r"\b(?:груд(?:ь|и|ью|ине)\b|грудн\w*\s+клетк\w*|кокуро[кг]\w*|тош(?:ум\w*|у|ун\w*|то)?\b)"
HEART = r"\b(?:сердц(?:е|а|у|ем)\b|сердечн\w*\s+бол\w*|журо[кг]\w*)"

PAIN = r"\b(?:бол(?:ь|и|ит|ят|ело|ьно|ью|ей)\b|колет|колющ\w*|ноет|ноющ\w*|оору\w*|сыздап\w*|сайгыла\w*)"
SEVERE_PAIN = (
    rf"\b(?:сильн|остр|резк|невыносим|нестерпим|ужасн|жутк|адск)\w*\s+{_GAP}?бол\w*"
    rf"|\bбол\w*\s+{_GAP}{{0,2}}(?:сильн|остр|резк|невыносим|нестерпим)\w*"
    rf"|\b(?:катуу|чыдагыс\w*|кескин)\s+{_GAP}?оору\w*"
    rf"|\bоору\w*\s+{_GAP}?(?:катуу|чыдагыс\w*)"
)
PRESSING = r"\b(?:давит|давящ\w*|сдавлив\w*|сжима\w*|жжет|жжени\w*|жгуч\w*|кыс(?:ып|ат|ылып|ылат)\w*|ачыш\w*)"
SUDDEN = r"\b(?:внезапн\w*|вдруг|неожиданно|капыстан|кокусунан|кутулбогон\s+жерден)"

BREATHING_SEVERE = (
    r"\bне\s+(?:могу|может|можем)\s+(?:\w+\s+)?(?:дышать|вдохнуть|продохнуть)"
    r"|\b(?:трудно|тяжело|сложно|больно)\s+дышать|\bнечем\s+дышать|\bне\s+дышит"
    r"|\bзадыха\w*|\bудушь\w*|\bудушен\w*"
    r"|\bне\s+хватает\s+воздуха|\bнехватк\w*\s+воздуха"
    r"|\b(?:сильн\w*|резк\w*)\s+одышк\w*|\bодышк\w*\s+в\s+покое"
    r"|\bдем(?:им|и|ибиз)?\s+(?:ал\w*\s+)?(?:албай|кыйын\w*|оор\w*|жетпей|жетишпей|кысыл\w*|токто\w*)"
    r"|\bтумчу\w*|\bаба\s+(?:жетпей|жетишпей)\w*"
)
BREATHING_ANY = BREATHING_SEVERE + r"|\bодышк\w*|\bдыхани\w*|\bдышат\w*|\bдем\s+ал\w*"


@dataclass(frozen=True)
class EmergencyRule:
    """A category matches if ANY phrase matches, or ALL concepts of any combination match."""

    category: str
    phrases: tuple[str, ...] = ()
    combinations: tuple[tuple[str, ...], ...] = ()


EMERGENCY_RULES: tuple[EmergencyRule, ...] = (
    EmergencyRule(
        "chest_pain",
        phrases=(r"\bинфаркт\w*", r"\bсердечн\w*\s+приступ\w*"),
        combinations=(
            (CHEST, SEVERE_PAIN),
            (CHEST, PRESSING),
            (CHEST, PAIN, BREATHING_ANY),
            (HEART, PAIN),
            (HEART, PRESSING),
        ),
    ),
    EmergencyRule("breathing", phrases=(BREATHING_SEVERE,)),
    EmergencyRule(
        "unconsciousness",
        phrases=(
            r"\b(?:потерял\w*|потер\w*|теря\w*|терял\w*)\s+(?:\w+\s+)?сознани\w*",
            r"\bбез\s+сознания|\bобморок\w*|\bне\s+приходит\s+в\s+себя",
            r"\bэс\w*\s+(?:учун\s+)?жогот\w*|\bэсинен\s+тан\w*|\bэс(?:и|им)\s+оо\w*",
            r"\bэсине\s+келбей\w*|\bэс\s+учу\s+жок",
        ),
    ),
    EmergencyRule(
        "stroke",
        phrases=(
            r"\bинсульт\w*|\bперекосил\w*|\bперекошен\w*|\bпарализ\w*",
            r"\bонемел\w*\s+(?:\w+\s+)?(?:лиц\w*|половин\w*)|\b(?:лиц\w*|половин\w*\s+\w+)\s+онемел\w*",
            r"\bонемени\w*\s+(?:лиц\w*|половин\w*)",
            r"\bневнятн\w*\s+речь|\bречь\s+(?:\w+\s+)?(?:нарушил\w*|невнятн\w*|спутан\w*)|\bне\s+может\s+говорить",
            r"\bотнял\w*\s+(?:рук\w*|ног\w*)",
            r"\b(?:бет|ооз)\w*\s+(?:\w+\s+)?кыйша\w*",
            r"\bбир\s+жаг\w*\s+(?:\w+\s+)?(?:сезбей|кыймылдабай|шал)\w*",
            r"\bтил\w*\s+келбей\w*|\bсуйлой\s+албай\w*|\bшал\s+бол\w*",
        ),
    ),
    EmergencyRule(
        "bleeding",
        phrases=(
            r"\b(?:сильн|обильн)\w*\s+кровотечени\w*",
            r"\b(?:кровотечени\w*|кровь)\s+(?:\w+\s+)?не\s+останавлива\w*|\bне\s+останавлива\w*\s+кровь",
            r"\bмного\s+крови|\bрвот\w*\s+(?:с\s+)?кровью|\bрвет\s+кровью|\bкашля\w*\s+кровью",
            r"\bкровь\s+изо\s+рта|\bхлещет\s+кровь|\bкровь\s+хлещет",
            r"\bкан\s+(?:\w+\s+)?токтобо\w*|\bкан\s+кус\w*|\bкан\s+аралаш\s+(?:кус|жотол)\w*",
            r"\bкоп\s+кан\s+(?:ак|жогот|кет)\w*|\bкан\s+катуу\s+ак\w*",
        ),
    ),
    EmergencyRule(
        "allergy",
        phrases=(
            r"\bанафилак\w*|\bквинке",
            r"\bотек\w*\s+(?:горла|гортани|языка|губ|лица)",
            r"\b(?:горло|язык|губы|лицо)\s+(?:\w+\s+)?(?:отек\w*|опух\w*|отекл\w*)",
            r"\b(?:отекл|опух)\w*\s+(?:горло|язык|губы)",
        ),
        # "тамагым шишип" alone is common with a sore throat, so in Kyrgyz swelling
        # counts only together with an allergy context or breathing problems.
        combinations=(
            (r"\b(?:тамаг|тил|эрин)\w*\s+(?:\w+\s+)?(?:шиш|иш)(?:ип|ди|ик)\w*",
             r"\bаллерги\w*|\bаары\w*|\bчак(?:ты|кан|ып)\w*"),
            (r"\b(?:тамаг|тил|эрин)\w*\s+(?:\w+\s+)?(?:шиш|иш)(?:ип|ди|ик)\w*", BREATHING_ANY),
        ),
    ),
    EmergencyRule(
        "seizure",
        phrases=(
            r"\bсудорог\w*|\bсудорож\w*|\bконвульс\w*|\bприпад\w*|\bэпилептическ\w*",
            r"\bталма\w*|\bдене\w*\s+(?:\w+\s+)?тырыш\w*",
        ),
    ),
    EmergencyRule(
        "severe_pain",
        phrases=(
            r"\b(?:невыносим|нестерпим|адск)\w*\s+(?:\w+\s+)?бол\w*",
            r"\bбол\w*\s+(?:\w+\s+){0,2}(?:невыносим|нестерпим)\w*",
            r"\bсамая\s+сильная\s+(?:\w+\s+)?боль",
            r"\bчыдагыс\w*\s+(?:\w+\s+)?оору\w*|\bоору\w*\s+(?:\w+\s+)?чыдагыс\w*",
        ),
        combinations=((SUDDEN, SEVERE_PAIN), (r"\bчыдай\s+албай\w*", PAIN)),
    ),
    EmergencyRule(
        "self_harm",
        phrases=(
            r"\bпокончить\s+с\s+собой|\bпокончу\s+с\s+собой|\bсуицид\w*",
            r"\bне\s+хочу\s+(?:больше\s+)?жить|\bубить\s+себя|\bубью\s+себя",
            r"\bсвести\s+счеты\s+с\s+жизнью|\bналожить\s+на\s+себя\s+руки",
            r"\bозумду\s+(?:\w+\s+)?олтур\w*|\bозумо\s+кол\s+сал\w*",
            r"\bжашагым\s+келбей\w*|\bолгум\s+келет",
        ),
    ),
    EmergencyRule(
        "poisoning",
        phrases=(
            r"\bпередозир\w*|\bугарн\w*\s+газ\w*|\bотравил\w*\s+(?:угарн|газ)\w*",
            r"\bвыпил\w*\s+(?:\w+\s+)?(?:много|всю|все|пачку|упаковку|горсть)\s+(?:\w+\s+)?(?:таблет|лекарств)\w*",
            r"\bвыпил\w*\s+(?:уксус|отбеливател|бензин|яд)\w*",
            r"\bкоп\s+(?:\w+\s+)?(?:дары|таблетка)\w*\s+(?:\w+\s+)?ич\w*|\bис\s+тий\w*|\bуу\s+ич\w*",
        ),
    ),
    EmergencyRule(
        "critical_signs",
        phrases=(
            r"\bпосинел\w*|\bсинеют\s+губы",
            r"\bэрин\w*\s+(?:\w+\s+)?кокор\w*",
        ),
    ),
)

# Harmless phrases removed BEFORE matching, to avoid typical false alarms.
EMERGENCY_EXCLUSIONS: tuple[str, ...] = (
    r"\bжуро[кг]\w*\s+(?:\w+\s+)?айлан\w*",  # "жүрөгүм айланып" = nausea
    r"\b(?:трудно|тяжело|сложно)\s+дышать\s+носом|\bносом\s+(?:\w+\s+)?не\s+дыш\w*",
    r"\bмур(?:ун|д)\w*\s+(?:менен\s+)?дем\s+ал\w*\s+(?:\w+\s+)?(?:албай|кыйын)\w*",
    r"\bсудорог\w*\s+(?:в\s+)?(?:\w+\s+)?(?:ног\w*|икр\w*|пальц\w*|стоп\w*|мышц\w*)",
    r"\b(?:ног\w*|икр\w*)\s+(?:\w+\s+)?судорог\w*",
)


@dataclass(frozen=True)
class EmergencyCheck:
    is_emergency: bool
    matched: str | None = None  # text fragment that triggered the rule
    category: str | None = None  # e.g. "chest_pain", "stroke"


@dataclass(frozen=True)
class _CompiledRule:
    category: str
    phrases: tuple[re.Pattern[str], ...]
    combinations: tuple[tuple[re.Pattern[str], ...], ...] = field(default=())


class EmergencyDetector:
    """Detects emergency symptoms regardless of the message language."""

    def __init__(
        self,
        rules: tuple[EmergencyRule, ...] = EMERGENCY_RULES,
        exclusions: tuple[str, ...] = EMERGENCY_EXCLUSIONS,
    ) -> None:
        self._rules = tuple(
            _CompiledRule(
                category=rule.category,
                phrases=tuple(re.compile(p) for p in rule.phrases),
                combinations=tuple(tuple(re.compile(p) for p in combo) for combo in rule.combinations),
            )
            for rule in rules
        )
        self._exclusions = tuple(re.compile(p) for p in exclusions)

    def check(self, message: str) -> EmergencyCheck:
        text = normalise_text(message)
        for exclusion in self._exclusions:
            text = exclusion.sub(" ", text)

        for rule in self._rules:
            for pattern in rule.phrases:
                found = pattern.search(text)
                if found:
                    return EmergencyCheck(True, matched=found.group(0), category=rule.category)
            for combination in rule.combinations:
                found_all = [pattern.search(text) for pattern in combination]
                if all(found_all):
                    fragment = " + ".join(f.group(0) for f in found_all if f)
                    return EmergencyCheck(True, matched=fragment, category=rule.category)

        return EmergencyCheck(is_emergency=False)

    @staticmethod
    def emergency_message(language: str) -> str:
        return EMERGENCY_MESSAGES[language]


# ============================================================================
# Answer guard — building blocks (for normalised text WITH punctuation)
# ============================================================================

_NUMBER = r"(?<![\w.,])\d+(?:[.,]\d+)?"
_COUNT_WORD = r"(?:\b(?:одн[уа]|две|два|три|половин\w*|бир|эки|уч|жарым)\b)"

# Always a dosage: "500 мг", "10 mcg", "5 мг/кг".
_HARD_DOSE = re.compile(rf"{_NUMBER}\s*(?:мг|mg|мкг|mcg|µg|ме|iu|ед)(?:/кг)?\b")
# Counted dose forms: "2 таблетки", "бир капсула", "3 тамчы".
_COUNT_DOSE = re.compile(
    rf"(?:{_NUMBER}|{_COUNT_WORD})\s*(?:-\s*\d+\s*)?(?:таблет\w*|капсул\w*|ампул\w*|тамчы\w*|капл\w*|саше|пакетик\w*|укол\w*)"
)
# Ambiguous amounts ("300 мл воды") — a dosage only next to medication words.
_SOFT_AMOUNT = re.compile(rf"{_NUMBER}\s*(?:мл|ml|г|гр|грамм\w*)\b")
# Dosing schedules ("3 раза в день") — a prescription only next to medication words.
_SCHEDULE = re.compile(
    r"(?:\d+|один|два|три|четыре|бир|эки|уч|торт)\s*(?:раз\w*\s+в\s+(?:день|сутки)|жолу|маал)"
    r"|\bкаждые\s+\d+\s*час\w*|\bар\s+бир\s+\d+\s*саат\w*|\bкунуно\s+\d+"
)

_DRUG_NAMES = (
    r"(?:парацетамол|ибупрофен|нурофен|аспирин|анальгин|цитрамон|но\s*шпа|амоксицил\w*|азитромицин"
    r"|цефтриаксон|диклофенак|кеторол\w*|омепразол|метформин|инсулин|преднизолон|дексаметазон"
    r"|супрастин|лоратадин|цетиризин|эналаприл|каптоприл|амлодипин|варфарин|трамадол|антибиотик)\w*"
)
_MED_CONTEXT = re.compile(
    rf"\b(?:лекарств\w*|препарат\w*|таблет\w*|капсул\w*|сироп\w*|раствор\w*|дары\w*|дарын\w*"
    rf"|укол\w*|инъекци\w*|свеч\w*|маз\w*|{_DRUG_NAMES})"
)
# Direct instruction to take a specific drug: "примите парацетамол", "ибупрофен ичиниз".
_TAKE_VERB = r"(?<!не )\b(?:примите|принимайте|выпейте|пейте|колите|используйте|ичиниз|ичип\s+турунуз|ичсениз\s+болот|кабыл\s+алыныз)"
_PRESCRIPTION = re.compile(rf"{_TAKE_VERB}\s+(?:\w+\s+)?{_DRUG_NAMES}|\b{_DRUG_NAMES}\s+(?:\w+\s+)?{_TAKE_VERB}")

_DISEASES = (
    r"(?:грипп|ангин|пневмони|бронхит|гастрит|мигрен|диабет|гипертони|инфаркт|инсульт|аппендицит"
    r"|рак\b|онколог|опухол|ковид|covid|коронавирус|астм|язв|цистит|отит|синусит|гайморит"
    r"|пиелонефрит|менингит|туберкулез|гепатит|анеми|депресси|орви)\w*"
)
_DIAGNOSIS = re.compile(
    "|".join(
        (
            # RU: "у вас грипп", "у вас точно гастрит", "у вас развилась пневмония"
            rf"\bу\s+вас\s+(?:точно\s+|определенно\s+|явно\s+|несомненно\s+|скорее\s+всего\s+)?"
            rf"(?:есть\s+|развил\w*\s+|начал\w*\s+)?{_DISEASES}",
            rf"\bвы\s+(?:точно\s+|определенно\s+)?(?:больны|болеете)\s+{_DISEASES}",
            rf"\bэто\s+(?:точно|определенно|несомненно|однозначно)\s+{_DISEASES}",
            rf"\bваш\s+диагноз|\bставлю\s+(?:вам\s+)?диагноз|\bдиагноз\s*[:—-]?\s*{_DISEASES}",
            # KY: "сизде гастрит бар", "бул так грипп", "сиздин диагнозуңуз"
            rf"\bсизде\s+(?:так\s+|созсуз\s+|анык\s+)?(?:кант\s+)?{_DISEASES}",
            rf"\bбул\s+(?:так|созсуз|анык)\s+{_DISEASES}",
            r"\bсиздин\s+диагноз\w*|\bдиагнозунуз\b",
            # Pretending to be a doctor / to have examined the user
            r"\bя\s+(?:ваш\s+)?(?:врач|доктор)\b|\bя\s+осмотрел\w*|\bпо\s+результатам\s+(?:моего\s+)?осмотра",
            r"\bмен\s+(?:сиздин\s+)?дарыгер(?:инизмин|мин)\b|\bмен\s+сизди\s+карап\s+чыктым",
        )
    )
)

_SENTENCE_SPLIT = re.compile(r"[!?;\n]+|\.(?!\d)")


@dataclass(frozen=True)
class GuardResult:
    is_safe: bool
    reason: str | None = None  # "dosage" | "prescription" | "diagnosis"


class AnswerGuard:
    """Post-processes LLM output before it reaches the user."""

    @staticmethod
    def contains_dosage(answer: str) -> bool:
        """True if the answer gives a concrete medication amount or dosing schedule."""
        text = normalise_text(answer, keep_punctuation=True)
        if _HARD_DOSE.search(text) or _COUNT_DOSE.search(text):
            return True
        # Ambiguous amounts/schedules count only inside a sentence about medication.
        for sentence in _SENTENCE_SPLIT.split(text):
            if (_SOFT_AMOUNT.search(sentence) or _SCHEDULE.search(sentence)) and _MED_CONTEXT.search(sentence):
                return True
        return False

    @staticmethod
    def contains_prescription(answer: str) -> bool:
        """True if the answer tells the user to take a specific named drug."""
        return bool(_PRESCRIPTION.search(normalise_text(answer)))

    @staticmethod
    def contains_diagnosis(answer: str) -> bool:
        """True if the answer states a categorical diagnosis or claims to be a doctor."""
        return bool(_DIAGNOSIS.search(normalise_text(answer)))

    def review(self, answer: str) -> GuardResult:
        if self.contains_dosage(answer):
            return GuardResult(False, "dosage")
        if self.contains_prescription(answer):
            return GuardResult(False, "prescription")
        if self.contains_diagnosis(answer):
            return GuardResult(False, "diagnosis")
        return GuardResult(True)

    def sanitise(self, answer: str, language: str) -> str:
        answer = answer.strip()
        if not answer:
            return MEDICATION_REFUSALS[language]

        result = self.review(answer)
        if result.is_safe:
            return answer

        # Metadata only — never log the answer text.
        logger.warning("AnswerGuard replaced an unsafe answer: reason=%s", result.reason)
        if result.reason == "diagnosis":
            return DIAGNOSIS_REFUSALS[language]
        return MEDICATION_REFUSALS[language]
