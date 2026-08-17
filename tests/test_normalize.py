from survdocker.normalize import normalize_message


def test_ip_and_port_normalization():
    message = "read tcp 172.19.0.4:9091->172.19.0.35:48234: i/o timeout"
    assert normalize_message(message) == "read tcp <IP>:<PORT>-><IP>:<PORT>: i/o timeout"


def test_uuid_and_timestamp_normalization():
    message = "2026-08-17T06:00:00Z request id 123e4567-e89b-12d3-a456-426614174000"
    normalized = normalize_message(message)
    assert "<TIMESTAMP>" in normalized
    assert "<UUID>" in normalized
