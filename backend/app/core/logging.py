"""
Logging setup.

Privacy rule: medical messages are sensitive personal data. Application code
must NEVER log message contents — only metadata (lengths, language, flags).
"""

from __future__ import annotations

import logging

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"


def setup_logging(level: str = "INFO") -> None:
    """Configure root logging once at application start-up."""
    logging.basicConfig(level=level, format=_LOG_FORMAT, force=True)
    # Third-party HTTP clients are noisy at INFO level.
    for noisy in ("httpx", "httpcore", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
