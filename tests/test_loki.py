from datetime import datetime, timezone

from survdocker.loki import LokiClient, default_query


def test_default_query_uses_job_label():
    assert default_query("docker") == '{job="docker"}'


def test_parse_loki_response_reads_container_labels():
    client = LokiClient("http://loki:3100")
    payload = {
        "status": "success",
        "data": {
            "result": [
                {
                    "stream": {"container": "traefik", "job": "docker"},
                    "values": [["1720000000000000000", "error backend unavailable"]],
                }
            ]
        },
    }
    entries = client._parse_response(payload)
    assert len(entries) == 1
    assert entries[0].container == "traefik"
    assert entries[0].timestamp == datetime.fromtimestamp(1720000000, tz=timezone.utc)
