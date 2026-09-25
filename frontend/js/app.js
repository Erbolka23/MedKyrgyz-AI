/**
 * MedKyrgyz AI — chat UI controller.
 *
 * Responsibilities:
 *   - render user / assistant messages, typing indicator and errors
 *   - manage UI state (language, conversation id, loading)
 *   - delegate all network calls to window.Api (js/api.js)
 */
(function () {
  "use strict";

  const config = window.MEDKYRGYZ_CONFIG;
  const { t } = window.I18n;

  const STORAGE_KEYS = {
    language: "medkyrgyz.language",
    conversation: "medkyrgyz.conversationId",
  };

  // ------------------------------------------------------------------ DOM
  const el = {
    messages: document.getElementById("messages"),
    form: document.getElementById("composer"),
    input: document.getElementById("message-input"),
    sendBtn: document.getElementById("send-btn"),
    counter: document.getElementById("char-counter"),
    languageSelect: document.getElementById("language-select"),
    newChatBtn: document.getElementById("new-chat-btn"),
    errorBanner: document.getElementById("error-banner"),
    errorText: document.getElementById("error-text"),
    retryBtn: document.getElementById("retry-btn"),
    dismissErrorBtn: document.getElementById("dismiss-error-btn"),
    statusDot: document.getElementById("status-dot"),
    welcomeTemplate: document.getElementById("welcome-template"),
  };

  // ---------------------------------------------------------------- state
  const state = {
    language: readStorage(localStorage, STORAGE_KEYS.language) || config.DEFAULT_LANGUAGE,
    conversationId: readStorage(sessionStorage, STORAGE_KEYS.conversation),
    isLoading: false,
    lastFailedMessage: null,
    disclaimerShown: false,
  };

  // Storage can throw (private mode, blocked cookies) — never let it break the chat.
  function readStorage(storage, key) {
    try {
      return storage.getItem(key);
    } catch (_) {
      return null;
    }
  }

  function writeStorage(storage, key, value) {
    try {
      if (value === null) storage.removeItem(key);
      else storage.setItem(key, value);
    } catch (_) {
      /* ignore */
    }
  }

  // ------------------------------------------------------------ rendering
  function renderWelcome() {
    el.messages.innerHTML = "";
    const node = el.welcomeTemplate.content.cloneNode(true);
    const box = node.querySelector(".suggestions");

    window.I18n.suggestions(state.language).forEach((text) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "suggestion";
      chip.textContent = text;
      chip.addEventListener("click", () => sendMessage(text));
      box.appendChild(chip);
    });

    el.messages.appendChild(node);
    window.I18n.apply(state.language);
  }

  function removeWelcome() {
    const welcome = el.messages.querySelector(".welcome");
    if (welcome) welcome.remove();
  }

  function formatTime(date) {
    return date.toLocaleTimeString(state.language === "ru" ? "ru-RU" : "ky-KG", {
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  /**
   * Append a message bubble. Text is always inserted with textContent
   * (never innerHTML) to prevent XSS from model output.
   */
  function appendMessage({ role, text, isEmergency = false, disclaimer = null }) {
    removeWelcome();

    const row = document.createElement("div");
    row.className = `message message--${role}${isEmergency ? " message--emergency" : ""}`;

    if (role === "assistant") {
      const avatar = document.createElement("img");
      avatar.className = "message__avatar";
      avatar.src = "assets/logo.svg";
      avatar.alt = "";
      row.appendChild(avatar);
    }

    const bubble = document.createElement("div");
    bubble.className = "message__bubble";

    if (isEmergency) {
      const badge = document.createElement("span");
      badge.className = "message__badge";
      badge.textContent = t(state.language, "emergencyBadge");
      bubble.appendChild(badge);
    }

    const body = document.createElement("p");
    body.className = "message__text";
    body.textContent = text;
    bubble.appendChild(body);

    if (disclaimer) {
      const note = document.createElement("p");
      note.className = "message__disclaimer";
      note.textContent = disclaimer;
      bubble.appendChild(note);
    }

    const meta = document.createElement("span");
    meta.className = "message__meta";
    meta.textContent = `${t(state.language, role === "user" ? "you" : "assistant")} · ${formatTime(new Date())}`;
    bubble.appendChild(meta);

    row.appendChild(bubble);
    el.messages.appendChild(row);
    scrollToBottom();
  }

  function showTyping() {
    const row = document.createElement("div");
    row.className = "message message--assistant message--typing";
    row.id = "typing-indicator";
    row.innerHTML = `
      <img class="message__avatar" src="assets/logo.svg" alt="" />
      <div class="message__bubble">
        <span class="typing-dots" aria-hidden="true"><span></span><span></span><span></span></span>
        <span class="visually-hidden"></span>
      </div>`;
    row.querySelector(".visually-hidden").textContent = t(state.language, "typing");
    el.messages.appendChild(row);
    scrollToBottom();
  }

  function hideTyping() {
    const row = document.getElementById("typing-indicator");
    if (row) row.remove();
  }

  function scrollToBottom() {
    el.messages.scrollTo({ top: el.messages.scrollHeight, behavior: "smooth" });
  }

  function showError(kind) {
    el.errorText.textContent = t(state.language, `errors.${kind}`, { max: config.MAX_MESSAGE_LENGTH });
    el.retryBtn.hidden = !state.lastFailedMessage;
    el.errorBanner.hidden = false;
  }

  function hideError() {
    el.errorBanner.hidden = true;
  }

  function setLoading(isLoading) {
    state.isLoading = isLoading;
    el.input.disabled = isLoading;
    el.form.setAttribute("aria-busy", String(isLoading));
    updateComposer();
  }

  function updateComposer() {
    const length = el.input.value.trim().length;
    el.sendBtn.disabled = state.isLoading || length === 0;
    el.counter.textContent =
      length > config.MAX_MESSAGE_LENGTH * 0.8
        ? t(state.language, "charCounter", { n: length, max: config.MAX_MESSAGE_LENGTH })
        : "";
    // Auto-grow textarea up to the CSS max-height.
    el.input.style.height = "auto";
    el.input.style.height = `${el.input.scrollHeight}px`;
  }

  // ------------------------------------------------------------- actions
  async function sendMessage(rawText) {
    const text = (rawText || "").trim();
    if (!text || state.isLoading) return;
    if (text.length > config.MAX_MESSAGE_LENGTH) {
      showError("tooLong");
      return;
    }

    hideError();
    appendMessage({ role: "user", text });
    el.input.value = "";
    setLoading(true);
    showTyping();

    try {
      const data = await window.Api.sendMessage({
        message: text,
        language: state.language,
        conversationId: state.conversationId,
      });

      state.conversationId = data.conversation_id;
      writeStorage(sessionStorage, STORAGE_KEYS.conversation, state.conversationId);
      state.lastFailedMessage = null;

      hideTyping();
      appendMessage({
        role: "assistant",
        text: data.answer,
        isEmergency: data.is_emergency,
        // Show the disclaimer on the first answer and on every emergency answer.
        disclaimer: !state.disclaimerShown || data.is_emergency ? data.disclaimer : null,
      });
      state.disclaimerShown = true;
      setStatus(true);
    } catch (err) {
      hideTyping();
      state.lastFailedMessage = text;
      const kind = err instanceof window.Api.ApiError ? err.kind : "server";
      if (kind === "network") setStatus(false);
      showError(kind);
      console.error("[MedKyrgyz] request failed:", err);
    } finally {
      setLoading(false);
      el.input.focus();
    }
  }

  function retryLastMessage() {
    const text = state.lastFailedMessage;
    if (!text) return;
    // Remove the failed user bubble so it is not duplicated.
    const userBubbles = el.messages.querySelectorAll(".message--user");
    const last = userBubbles[userBubbles.length - 1];
    if (last) last.remove();
    sendMessage(text);
  }

  function startNewChat() {
    state.conversationId = null;
    state.lastFailedMessage = null;
    state.disclaimerShown = false;
    writeStorage(sessionStorage, STORAGE_KEYS.conversation, null);
    hideError();
    renderWelcome();
    el.input.focus();
  }

  function changeLanguage(lang) {
    state.language = lang;
    writeStorage(localStorage, STORAGE_KEYS.language, lang);
    window.I18n.apply(lang);
    if (el.messages.querySelector(".welcome")) renderWelcome();
    if (!el.errorBanner.hidden) hideError();
    updateComposer();
  }

  function setStatus(isOnline) {
    el.statusDot.classList.toggle("status-dot--online", isOnline);
    el.statusDot.classList.toggle("status-dot--offline", !isOnline);
  }

  /** Re-render the current session's conversation after a page reload. */
  async function restoreConversation() {
    if (!state.conversationId) return;
    try {
      const history = await window.Api.getHistory(state.conversationId);
      history.messages.forEach((m) =>
        appendMessage({ role: m.role, text: m.content, isEmergency: m.is_emergency })
      );
      state.disclaimerShown = history.messages.length > 0;
    } catch (err) {
      // Unknown or expired conversation: start fresh silently.
      if (err instanceof window.Api.ApiError && err.status === 404) {
        state.conversationId = null;
        writeStorage(sessionStorage, STORAGE_KEYS.conversation, null);
      }
    }
  }

  async function checkBackend() {
    try {
      await window.Api.health();
      setStatus(true);
    } catch (_) {
      setStatus(false);
    }
  }

  // --------------------------------------------------------------- events
  el.form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendMessage(el.input.value);
  });

  el.input.addEventListener("keydown", (event) => {
    // Enter sends, Shift+Enter inserts a new line. Ignore IME composition.
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
      event.preventDefault();
      sendMessage(el.input.value);
    }
  });

  el.input.addEventListener("input", updateComposer);
  el.languageSelect.addEventListener("change", (e) => changeLanguage(e.target.value));
  el.newChatBtn.addEventListener("click", startNewChat);
  el.retryBtn.addEventListener("click", retryLastMessage);
  el.dismissErrorBtn.addEventListener("click", hideError);

  // ----------------------------------------------------------------- init
  function init() {
    if (!window.I18n.languages.includes(state.language)) state.language = config.DEFAULT_LANGUAGE;
    el.languageSelect.value = state.language;
    window.I18n.apply(state.language);
    renderWelcome();
    updateComposer();
    checkBackend();
    restoreConversation();
  }

  init();
})();
