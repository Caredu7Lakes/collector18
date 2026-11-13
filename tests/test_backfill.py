from scripts.backfill import build_query


def test_build_query_shape():
    q = build_query("123-456@g.us", "2020-01-01T00:00:00Z", "2026-11-09T23:59:59Z", page=2, offset=100)
    assert q["where"]["key"]["remoteJid"] == "123-456@g.us"
    assert q["where"]["messageTimestamp"] == {
        "gte": "2020-01-01T00:00:00Z",
        "lte": "2026-11-09T23:59:59Z",
    }
    assert q["page"] == 2
    assert q["offset"] == 100
