from survdocker.monitor import build_critical_alerts


AUTHELIA_408 = '{"error":"read tcp 172.19.0.4:9091-\\u003e172.19.0.38:50278: i/o timeout","level":"error","msg":"Request timeout occurred while handling request from client.","status_code":408}'
CONFIG = {
    "critical_containers": ["authelia_df"],
    "critical_alerts": {"error_threshold": 3},
    "dependencies": {"authelia_df": ["authelia_redis_df"]},
}
CONTAINERS = [{"Names": ["/authelia_df"], "State": "running"}]


def test_ignored_client_timeouts_do_not_raise_dependency_alert():
    config = {**CONFIG, "ignore_patterns": ["Request timeout occurred while handling request from client"]}
    assert build_critical_alerts(config, CONTAINERS, {"authelia_df": [AUTHELIA_408] * 3}) == []


def test_real_dependency_errors_still_alert():
    config = {**CONFIG, "ignore_patterns": ["Request timeout occurred while handling request from client"]}
    lines = ["dial tcp authelia_redis_df:6379: connect: connection refused"] * 3
    alerts = build_critical_alerts(config, CONTAINERS, {"authelia_df": lines})
    assert [alert.alert_type for alert in alerts] == ["dependency"]
