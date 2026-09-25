/**
 * Backend API client.
 * This is the single integration point between the frontend and the backend.
 * Contract: see docs/api.md and backend/app/schemas/chat.py.
 */
(function () {
  "use strict";

  const config = window.MEDKYRGYZ_CONFIG;

  /** Error with a stable `kind` the UI can translate. */
  class ApiError extends Error {
    constructor(kind, message, status) {
      super(message || kind);
      this.name = "ApiError";
      this.kind = kind; // network | timeout | validation | unavailable | server
      this.status = status || 0;
    }
  }

  function kindFromStatus(status) {
    if (status === 422 || status === 400) return "validation";
    if (status === 503 || status === 502 || status === 504) return "unavailable";
    return "server";
  }

  async function request(path, options) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), config.REQUEST_TIMEOUT_MS);

    let response;
    try {
      response = await fetch(`${config.API_BASE_URL}${path}`, {
        ...options,
        headers: { "Content-Type": "application/json", ...(options && options.headers) },
        signal: controller.signal,
      });
    } catch (err) {
      throw new ApiError(err.name === "AbortError" ? "timeout" : "network", err.message);
    } finally {
      clearTimeout(timer);
    }

    let body = null;
    try {
      body = await response.json();
    } catch (_) {
      /* non-JSON body — handled below */
    }

    if (!response.ok) {
      throw new ApiError(kindFromStatus(response.status), body && body.detail, response.status);
    }
    return body;
  }

  /**
   * POST /chat
   * @param {{message: string, language: "ky"|"ru"|"auto", conversationId?: string|null}} params
   * @returns {Promise<{answer: string, conversation_id: string, language: string, is_emergency: boolean, disclaimer: string}>}
   */
  function sendMessage({ message, language, conversationId }) {
    const payload = { message, language };
    if (conversationId) payload.conversation_id = conversationId;
    return request("/chat", { method: "POST", body: JSON.stringify(payload) });
  }

  /** GET /conversations/{id}/messages — used to restore the chat after a page reload. */
  function getHistory(conversationId) {
    return request(`/conversations/${encodeURIComponent(conversationId)}/messages`, { method: "GET" });
  }

  /** GET /health */
  function health() {
    return request("/health", { method: "GET" });
  }

  window.Api = Object.freeze({ sendMessage, getHistory, health, ApiError });
})();
