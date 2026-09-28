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


def test_explicit_language_always_wins(client: TestClient) -> None:
    # Russian text, Kyrgyz selected -> Kyrgyz answer; and vice versa.
    ky = client.post("/chat", json={"message": "У меня болит голова", "language": "ky"}).json()
    assert ky["language"] == "ky"
    assert ky["answer"].startswith("Качантан бери")

    ru = client.post("/chat", json={"message": "Башым ооруп жатат", "language": "ru"}).json()
    assert ru["language"] == "ru"
    assert ru["answer"].startswith("Как давно")


def test_emergency_answer_uses_selected_language(client: TestClient) -> None:
    body = client.post("/chat", json={"message": "Кокурогум катуу ооруп жатат", "language": "ru"}).json()
    assert body["is_emergency"] is True
    assert "Немедленно вызовите скорую помощь" in body["answer"]


def test_auto_short_russian_is_answered_in_russian(client: TestClient) -> None:
    body = client.post("/chat", json={"message": "Горло першит", "language": "auto"}).json()
    assert body["language"] == "ru"


def test_auto_undetermined_keeps_conversation_language(client: TestClient) -> None:
    first = client.post("/chat", json={"message": "Горло першит", "language": "auto"}).json()
    follow_up = client.post(
        "/chat",
        json={"message": "38", "language": "auto", "conversation_id": first["conversation_id"]},
    ).json()
    assert follow_up["language"] == "ru"
