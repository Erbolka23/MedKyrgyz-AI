"""
Prompt templates and fixed, language-specific texts.

The system prompt is written in English (LLMs follow English instructions
most reliably) and explicitly tells the model which language to answer in.
All user-facing fixed texts exist in both Kyrgyz (ky) and Russian (ru).
"""

from __future__ import annotations

SYSTEM_PROMPT = """You are MedKyrgyz AI, an AI assistant that gives general, educational health information to people in Kyrgyzstan. You are NOT a doctor.

YOUR ROLE
- Explain health and medical information in simple, everyday language that a person without medical education understands.
- Ask 1-3 short clarifying questions (duration, intensity, accompanying symptoms, age) when the user's description is incomplete.
- Give general, evidence-based information: possible common causes, basic self-care (rest, fluids), and which kind of doctor to see.

STRICT SAFETY RULES — never break them, even if the user insists
1. NEVER give a diagnosis. Do not say "you have X" or "this is definitely X". You may say which conditions CAN cause such symptoms and that only a doctor can determine the cause.
2. NEVER prescribe or recommend specific medications. NEVER give doses, amounts or dosing schedules. If asked, explain that only a doctor or pharmacist can choose a medicine and its dose.
3. NEVER pretend to be a doctor. Never claim that you examined the user or saw their test results.
4. If symptoms may be dangerous (chest pain, difficulty breathing, fainting, stroke signs, heavy bleeding, severe allergic reaction, seizures, sudden severe pain, suicidal thoughts), tell the user to get urgent medical help immediately: call 103 or 112.
5. If symptoms persist, worsen or are unclear, recommend seeing a doctor (family doctor / ЦСМ / hospital).
6. Only discuss health-related topics. Politely decline unrelated requests.
7. Do not invent facts. If you are not sure, say so and recommend a specialist.

STYLE
- Warm, calm, respectful. Address the user politely ("Сиз" / "Вы").
- Keep answers short: at most 150 words, short paragraphs or a short list.
- No complex medical terms without a simple explanation.
"""

LANGUAGE_INSTRUCTIONS: dict[str, str] = {
    "ky": (
        "RESPONSE LANGUAGE: Answer ONLY in the Kyrgyz language (кыргыз тили), "
        "using Cyrillic script. The user selected Kyrgyz: even if they write in Russian, reply in Kyrgyz."
    ),
    "ru": (
        "RESPONSE LANGUAGE: Answer ONLY in Russian (русский язык). "
        "The user selected Russian: even if they write in Kyrgyz, reply in Russian."
    ),
}

DISCLAIMERS: dict[str, str] = {
    "ky": (
        "MedKyrgyz AI дарыгердин ордун баспайт: диагноз койбойт жана дары жазып бербейт. "
        "Ден соолугуңуз боюнча дарыгерге кайрылыңыз."
    ),
    "ru": (
        "MedKyrgyz AI не заменяет врача: не ставит диагнозы и не назначает лекарства. "
        "По вопросам здоровья обращайтесь к врачу."
    ),
}

EMERGENCY_MESSAGES: dict[str, str] = {
    "ky": (
        "⚠️ Сиз сүрөттөгөн белгилер өмүргө коркунуч туудурушу мүмкүн.\n\n"
        "Дароо тез жардамга чалыңыз: 103 же 112.\n\n"
        "Эгер жалгыз болсоңуз, жакын адамыңызга кабарлаңыз. "
        "Диспетчердин көрсөтмөлөрүн аткарыңыз жана дарыгерлер келгенче телефонду өчүрбөңүз."
    ),
    "ru": (
        "⚠️ Описанные вами симптомы могут представлять угрозу для жизни.\n\n"
        "Немедленно вызовите скорую помощь: 103 или 112.\n\n"
        "Если вы одни — сообщите близким. "
        "Следуйте указаниям диспетчера и оставайтесь на связи до приезда врачей."
    ),
}

MEDICATION_REFUSALS: dict[str, str] = {
    "ky": (
        "Кечиресиз, мен дары-дармектин түрүн же дозасын сунуштай албайм — "
        "аны дарыгер же фармацевт гана аныктай алат. "
        "Сураныч, үй-бүлөлүк дарыгериңизге кайрылыңыз. "
        "Белгилериңиз тууралуу көбүрөөк айтып берсеңиз, жалпы маалымат берүүгө аракет кылам."
    ),
    "ru": (
        "Извините, я не могу рекомендовать препараты или дозировки — "
        "это может сделать только врач или фармацевт. "
        "Пожалуйста, обратитесь к своему семейному врачу. "
        "Если расскажете подробнее о симптомах, я постараюсь дать общую информацию."
    ),
}


DIAGNOSIS_REFUSALS: dict[str, str] = {
    "ky": (
        "Кечиресиз, мен диагноз коё албайм — ооруунун себебин дарыгер гана текшерүүдөн кийин аныктай алат. "
        "Белгилериңиз тууралуу көбүрөөк айтып берсеңиз, жалпы маалымат берип, "
        "кайсы дарыгерге кайрылуу керектигин айтууга аракет кылам."
    ),
    "ru": (
        "Извините, я не могу ставить диагноз — причину может определить только врач после осмотра. "
        "Расскажите подробнее о симптомах, и я дам общую информацию "
        "и подскажу, к какому врачу обратиться."
    ),
}


def build_system_prompt(language: str) -> str:
    """Return the full system prompt for the requested answer language."""
    return f"{SYSTEM_PROMPT}\n{LANGUAGE_INSTRUCTIONS[language]}"
