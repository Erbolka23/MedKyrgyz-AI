/**
 * Frontend configuration.
 * The only place where the backend address is defined.
 */
window.MEDKYRGYZ_CONFIG = Object.freeze({
  API_BASE_URL: "http://127.0.0.1:8000",
  REQUEST_TIMEOUT_MS: 45000,
  MAX_MESSAGE_LENGTH: 2000, // must match backend/app/schemas/chat.py
  DEFAULT_LANGUAGE: "ky",
});
