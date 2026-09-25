/**
 * UI translations (Kyrgyz / Russian).
 * Elements with data-i18n="key" get their text replaced,
 * elements with data-i18n-placeholder="key" get their placeholder replaced.
 */
(function () {
  "use strict";

  const TRANSLATIONS = {
    ky: {
      appSubtitle: "Медициналык маалымат боюнча жардамчы",
      newChat: "Жаңы маек",
      languageLabel: "Тил",
      welcomeTitle: "Салам! Мен MedKyrgyz AI.",
      welcomeText:
        "Ден соолук боюнча сурооңузга жөнөкөй тил менен жооп берем. Мен диагноз койбойм жана дары жазып бербейм.",
      suggestionsTitle: "Мисалы:",
      suggestions: [
        "Башым ооруп жатат",
        "Баламдын ысыгы көтөрүлдү, эмне кылсам болот?",
        "Кан басымы деген эмне?",
      ],
      inputPlaceholder: "Сурооңузду жазыңыз…",
      send: "Жөнөтүү",
      typing: "Жооп даярдалууда…",
      you: "Сиз",
      assistant: "MedKyrgyz AI",
      emergencyBadge: "Шашылыш абал",
      retry: "Кайра аракет кылуу",
      dismiss: "Жабуу",
      emergencyBanner: "Шашылыш учурда: 103 же 112",
      footerDisclaimer:
        "MedKyrgyz AI дарыгердин ордун баспайт. Маалымат гана берет — диагноз койбойт жана дары жазбайт.",
      charCounter: "{n} / {max}",
      errors: {
        network: "Сервер менен байланыш түзүлгөн жок. Интернетти текшерип, кайра аракет кылыңыз.",
        timeout: "Сервер өтө узак жооп бербей жатат. Кайра аракет кылыңыз.",
        validation: "Билдирүү туура эмес. Текстти текшериңиз.",
        unavailable: "AI кызматы убактылуу иштебей жатат. Бир аздан кийин кайра аракет кылыңыз.",
        server: "Серверде ката кетти. Кайра аракет кылыңыз.",
        tooLong: "Билдирүү өтө узун (эң көп {max} белги).",
      },
    },
    ru: {
      appSubtitle: "Помощник по медицинской информации",
      newChat: "Новый чат",
      languageLabel: "Язык",
      welcomeTitle: "Здравствуйте! Я MedKyrgyz AI.",
      welcomeText:
        "Отвечу на вопросы о здоровье простым языком. Я не ставлю диагнозы и не назначаю лекарства.",
      suggestionsTitle: "Например:",
      suggestions: [
        "У меня болит голова",
        "У ребёнка поднялась температура, что делать?",
        "Что такое артериальное давление?",
      ],
      inputPlaceholder: "Напишите ваш вопрос…",
      send: "Отправить",
      typing: "Готовлю ответ…",
      you: "Вы",
      assistant: "MedKyrgyz AI",
      emergencyBadge: "Экстренная ситуация",
      retry: "Повторить",
      dismiss: "Закрыть",
      emergencyBanner: "В экстренном случае: 103 или 112",
      footerDisclaimer:
        "MedKyrgyz AI не заменяет врача. Только информация — без диагнозов и назначения лекарств.",
      charCounter: "{n} / {max}",
      errors: {
        network: "Не удалось связаться с сервером. Проверьте интернет и попробуйте снова.",
        timeout: "Сервер слишком долго не отвечает. Попробуйте снова.",
        validation: "Некорректное сообщение. Проверьте текст.",
        unavailable: "AI-сервис временно недоступен. Попробуйте немного позже.",
        server: "Произошла ошибка на сервере. Попробуйте снова.",
        tooLong: "Сообщение слишком длинное (максимум {max} символов).",
      },
    },
  };

  /** Resolve a dotted key such as "errors.network". */
  function t(lang, key, vars) {
    const dict = TRANSLATIONS[lang] || TRANSLATIONS.ky;
    let value = key.split(".").reduce((obj, part) => (obj ? obj[part] : undefined), dict);
    if (typeof value !== "string") return key;
    if (vars) {
      Object.keys(vars).forEach((name) => {
        value = value.replace(`{${name}}`, String(vars[name]));
      });
    }
    return value;
  }

  /** Apply translations to every annotated element in the document. */
  function apply(lang) {
    document.documentElement.lang = lang;
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      el.textContent = t(lang, el.dataset.i18n);
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach((el) => {
      el.placeholder = t(lang, el.dataset.i18nPlaceholder);
    });
    document.querySelectorAll("[data-i18n-aria]").forEach((el) => {
      el.setAttribute("aria-label", t(lang, el.dataset.i18nAria));
    });
  }

  function suggestions(lang) {
    return (TRANSLATIONS[lang] || TRANSLATIONS.ky).suggestions;
  }

  window.I18n = Object.freeze({ t, apply, suggestions, languages: Object.keys(TRANSLATIONS) });
})();
