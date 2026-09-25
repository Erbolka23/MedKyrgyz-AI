"""
Test configuration.

Environment variables are set BEFORE the application is imported so that
tests always use a throw-away SQLite database and the offline mock LLM.
"""

from __future__ import annotations

import os
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

_TMP_DIR = tempfile.mkdtemp(prefix="medkyrgyz-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{Path(_TMP_DIR, 'test.db').as_posix()}"
os.environ["LLM_PROVIDER"] = "mock"
os.environ["OPENAI_API_KEY"] = ""
os.environ["DEFAULT_LANGUAGE"] = "ky"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from main import create_app  # noqa: E402


@pytest.fixture()
def client() -> Iterator[TestClient]:
    with TestClient(create_app()) as test_client:
        yield test_client
