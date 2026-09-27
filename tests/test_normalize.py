from survdocker.normalize import normalize_message


def test_ip_and_port_normalization():
    message = "read tcp 172.19.0.4:9091->172.19.0.35:48234: i/o timeout"
    assert normalize_message(message) == "read tcp <IP>:<PORT>-><IP>:<PORT>: i/o timeout"


def test_uuid_and_timestamp_normalization():
    message = "2026-08-17T06:00:00Z request id 123e4567-e89b-12d3-a456-426614174000"
    normalized = normalize_message(message)
    assert "<TIMESTAMP>" in normalized
    assert "<UUID>" in normalized


def test_same_error_with_different_counters_collapses_to_one_pattern():
    pairs = [
        # termix: time of day with AM/PM
        ("[8:32:18 AM] [ERROR] Stats collector connection failed", "[12:30:10 PM] [ERROR] Stats collector connection failed"),
        # Postgres backend pid
        ("2026-09-23 05:50:22.633 UTC [100577] FATAL:  terminating connection", "2026-09-23 05:50:22.633 UTC [286067] FATAL:  terminating connection"),
        # nginx worker pid and connection number
        ("2026/09/24 08:07:14 [error] 25#25: *10470 client intended to send too large body", "2026/09/24 06:30:23 [error] 31#31: *342 client intended to send too large body"),
        # Apache timestamp and pid/tid
        ("[Sat Sep 26 18:53:26.078824 2026] [access_compat:error] [pid 618:tid 618] AH01797", "[Sat Sep 26 18:12:21.093996 2026] [access_compat:error] [pid 65060:tid 65060] AH01797"),
        # *arr indexer back-off date
        ('<error code="429" description="Indexer is disabled till 09/25/2026 02:12:50 due to recent failures." />', '<error code="429" description="Indexer is disabled till 09/23/2026 21:43:54 due to recent failures." />'),
        # JSON-escaped "->" glued to the IP
        ('{"error":"read tcp 172.19.0.3:9091-\\u003e172.19.0.36:35944: i/o timeout"}', '{"error":"read tcp 172.19.0.4:9091-\\u003e172.19.0.32:37326: i/o timeout"}'),
        # zerolog console time and ANSI colors
        ("\x1b[2m10:49AM\x1b[0m \x1b[91mERR\x1b[0m async instance start failed", "\x1b[2m1:27PM\x1b[0m \x1b[91mERR\x1b[0m async instance start failed"),
    ]
    for first, second in pairs:
        assert normalize_message(first) == normalize_message(second), first


def test_host_port_is_not_read_as_a_time():
    assert normalize_message("connect EHOSTUNREACH 192.168.0.5:22") == "connect EHOSTUNREACH <IP>:<PORT>"


def test_ipv6_rule_leaves_rust_paths_alone():
    assert normalize_message("[CAUSE] reqwest::Error {") == "[CAUSE] reqwest::Error {"
    assert normalize_message("peer 2a01:e0a:1f2::5 refused") == "peer <IPV6> refused"


def test_mariadb_space_padded_hour_is_a_timestamp():
    assert normalize_message("2026-09-23  7:51:57 0 [Warning] x") == normalize_message("2026-09-26 18:59:12 0 [Warning] x")
