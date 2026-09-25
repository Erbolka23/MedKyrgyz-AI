from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_chat_kyrgyz_example(client: TestClient) -> None:
    response = client.post("/chat", json={"message": "Башым ооруп жатат"})
    assert response.status_code == 200
    body = response.json()
    assert body["answer"].startswith("Качантан бери ооруп жатат?")
    assert body["language"] == "ky"
    assert body["is_emergency"] is False
    assert body["conversation_id"]
    assert body["disclaimer"]


def test_chat_explicit_russian(client: TestClient) -> None:
    response = client.post("/chat", json={"message": "Болит голова", "language": "ru"})
    assert response.status_code == 200
    assert response.json()["language"] == "ru"


def test_chat_emergency(client: TestClient) -> None:
    response = client.post("/chat", json={"message": "У меня боль в груди и не могу дышать"})
    body = response.json()
    assert body["is_emergency"] is True
    assert "103" in body["answer"]


def test_conversation_is_continued_and_stored(client: TestClient) -> None:
    first = client.post("/chat", json={"message": "Башым ооруп жатат"}).json()
    conversation_id = first["conversation_id"]
    second = client.post(
        "/chat", json={"message": "Эки күндөн бери", "conversation_id": conversation_id}
    ).json()
    assert second["conversation_id"] == conversation_id

    history = client.get(f"/conversations/{conversation_id}/messages").json()
    assert [m["role"] for m in history["messages"]] == ["user", "assistant", "user", "assistant"]


def test_empty_message_rejected(client: TestClient) -> None:
    response = client.post("/chat", json={"message": "   "})
    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_unknown_conversation_history_returns_404(client: TestClient) -> None:
    response = client.get("/conversations/does-not-exist/messages")
    assert response.status_code == 404
    assert response.json()["code"] == "conversation_not_found"
