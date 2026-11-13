from scripts.provision_webhook import build_payload


def test_build_payload_shape():
    payload = build_payload("http://collector18-app:8000/webhook", "tok")
    webhook = payload["webhook"]
    assert webhook["enabled"] is True
    assert webhook["url"] == "http://collector18-app:8000/webhook"
    assert webhook["headers"] == {"Authorization": "Bearer tok"}
    assert webhook["events"] == ["MESSAGES_UPSERT"]
    assert webhook["byEvents"] is False
    assert webhook["base64"] is False
