from survdocker.filters import FilterConfig, classify_level, should_keep_line


def test_authelia_noise_is_filtered():
    assert should_keep_line("Access to https://bookstack.denisflamant.com/robots.txt is not authorized") is False
    assert should_keep_line("responding with status code 401") is False
    assert should_keep_line("responding with status code 302") is False


def test_real_errors_are_kept():
    assert should_keep_line("error initializing session backend: redis connection error") is True
    assert should_keep_line("connect: connection refused") is True
    assert should_keep_line("Request timeout occurred while handling request from client") is True
    assert should_keep_line("fatal startup failure") is True


def test_level_detection():
    assert classify_level("fatal startup failure") == "fatal"
    assert classify_level("deprecated config key", FilterConfig()) == "warning"
    assert classify_level("random line") == "unknown"


def test_explicit_level_field_overrides_keyword_substring_match():
    # "without error" contains the substring "error" but the line is an
    # explicit info-level log - it must not be classified/kept as an error.
    line = 'level=info msg="node exited without error" controller_id="" node=labelstore'
    assert classify_level(line) == "unknown"
    assert should_keep_line(line) is False


def test_explicit_level_field_still_flags_real_errors():
    line = 'level=error msg="final error sending batch" status=400'
    assert classify_level(line) == "error"
    assert should_keep_line(line) is True


def test_explicit_warn_level_is_kept_as_warning():
    line = 'level=warn msg="failed mapping AST" err="context canceled"'
    assert classify_level(line) == "warning"
    assert should_keep_line(line) is True


def test_json_style_debug_level_is_dropped_despite_failed_keyword():
    # sftpgo-style structured JSON logging: "level" is a quoted JSON key, not
    # Go logfmt's level=, but it's just as reliable a signal.
    line = '{"level":"debug","time":"2026-09-07T11:51:59.750","sender":"sftpd","message":"failed to accept an incoming connection from ip 1.2.3.4: EOF"}'
    assert classify_level(line) == "unknown"
    assert should_keep_line(line) is False


def test_compound_word_does_not_false_positive_as_fatal_or_timeout():
    # "nonfatal"/"stimeout" contain "fatal"/"timeout" as substrings but are
    # unrelated config key names (AgentDVR camera option dumps), not signals.
    config = FilterConfig()
    assert classify_level("SetManualOptions: Jardin: set overrun_nonfatal=1", config) == "unknown"
    assert classify_level("SetManualOptions: Sonette: set stimeout=8000000", config) == "unknown"
    assert should_keep_line("SetManualOptions: Jardin: set overrun_nonfatal=1", config) is False
    assert should_keep_line("SetManualOptions: Sonette: set stimeout=8000000", config) is False


def test_known_operational_noise_is_ignored():
    import yaml

    payload = yaml.safe_load(open("survdocker/config/survdocker.yml", encoding="utf-8"))
    config = FilterConfig(
        ignore_patterns=payload["filters"]["ignore_patterns"],
        keep_patterns=payload["filters"]["keep_patterns"],
        warning_patterns=payload["filters"]["warning_patterns"],
    )
    noisy_lines = [
        '2026-09-09 16:26:18,238 fail2ban.actions        [1]: WARNING [traefik-auth] 104.155.25.18 already banned',
        "2026-09-09.17:58:20 [container-init] Detected Container that has been restarted - Cleaning '/data' files",
        '[2026-09-10 19:30:56 +0200] [12266] [INFO] Autorestarting worker after current request.',
        '2026-09-08T10:18:41+02:00 INFO [openvpn] SIGUSR1[soft,ping-restart] received, process restarting',
        '2026-09-08T10:18:51+02:00 ERROR [openvpn] RTNETLINK answers: Operation not permitted',
        '2026-09-08T10:18:51+02:00 ERROR [openvpn] Linux route delete command failed',
        '2026-09-08T10:18:51+02:00 INFO [openvpn] Linux ip addr del failed: external program exited with error status: 2',
    ]
    for line in noisy_lines:
        assert should_keep_line(line, config) is False, line

    # A real VPN credential failure must stay visible - distinct from the
    # benign ping-restart reconnect above.
    assert should_keep_line("2026-09-08T10:18:41+02:00 ERROR [openvpn] AUTH: Received control message: AUTH_FAILED", config) is True
