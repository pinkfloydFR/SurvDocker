from survdocker.filters import FilterConfig, _explicit_level, classify_level, should_keep_line


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
        'logger=authn.service t=2026-09-25T16:51:20.950868733+02:00 level=warn msg="Failed to authenticate request" client=auth.client.session error="user token not found"',
        'logger=middleware.gzip t=2026-09-26T18:06:50.616661581+02:00 level=warn msg="Failed to write gzipped response" path=/public/fonts/inter/Inter-Regular.woff2 error="http: request method or response status code does not allow body"',
        'logger=plugins.dedupe t=2026-09-26T17:41:52+02:00 level=warn msg="Skipping loading of plugin as it\'s a duplicate" pluginId=zipkin',
        'time=2026-09-23T05:50:09.244Z level=WARN source=main.go:1249 msg="Received an OS signal, exiting gracefully..." signal=terminated',
        '[2026-09-27 00:33:47] [WARNING] 8478 parsing errors',
    ]
    for line in noisy_lines:
        assert should_keep_line(line, config) is False, line

    # A real VPN credential failure must stay visible - distinct from the
    # benign ping-restart reconnect above.
    assert should_keep_line("2026-09-08T10:18:41+02:00 ERROR [openvpn] AUTH: Received control message: AUTH_FAILED", config) is True


def test_bracketed_python_logging_level_is_used():
    # crowdsec-blocklist-import: a [WARNING] line must not become an error just
    # because "failed" appears in the message.
    line = '[2026-09-24 13:07:11] [WARNING] Machine heartbeat failed: 401 {"code":401,"message":"signature is invalid"}'
    assert classify_level(line) == "warning"
    assert classify_level("[2026-09-20 06:46:00] [ERROR] Failed to push metrics to localhost:9091") == "error"
    assert should_keep_line("[2026-09-26 00:31:07] [INFO] Found 169935 existing decisions, 0 failed") is False


def test_leading_info_prefix_beats_keyword_in_url():
    # GeoBlock logs every evaluated request at INFO; "warning" only appears in
    # the requested file name.
    line = "INFO: GeoBlock: 2026/09/20 09:37:49 my-geoblock@file: evaluating client IP(s) [192.168.0.254] for [proxmox.example.com/icon-warning.png]"
    assert classify_level(line) == "unknown"
    assert should_keep_line(line) is False


def test_zerolog_console_level_with_ansi_colors():
    err = "\x1b[2m10:49AM\x1b[0m \x1b[91mERR\x1b[0m \x1b[2msablier/instance_request.go:166\x1b[0m async instance start failed"
    assert classify_level(err) == "error"
    info = "\x1b[2m10:49AM\x1b[0m \x1b[32mINF\x1b[0m instance stopped, previous start failed"
    assert should_keep_line(info) is False
    assert classify_level("2026-09-20T09:37:49+02:00 WRN deprecated option") == "warning"


def test_other_prefix_level_formats():
    assert classify_level("1:M 22 Sep 2026 02:31:23.530 * <bf> \t{ bf-error-rate       :      0.01 }") == "unknown"
    assert classify_level("1:M 23 Sep 2026 05:51:44.382 # Warning: no config file specified") == "warning"
    assert classify_level("2026-09-26 06:57:33,001 - root                             (734ccebb0b30) :  INFO (get_providers:1) - Throttling error") == "unknown"
    assert classify_level("2026-09-23  7:51:57 0 [Warning] mariadbd: io_uring_queue_init() failed") == "warning"
    assert classify_level("[Warn] HttpClient: HTTP Error - Res: HTTP/1.1 [GET]") == "warning"
    assert classify_level("[Fri Sep 25 07:35:31.260579 2026] [php:warn] [pid 17:tid 17] PHP Warning") == "warning"
    assert classify_level("2026/09/24 08:07:14 [error] 25#25: client intended to send too large body") == "error"
    assert classify_level("2026-09-23 05:50:22.633 UTC [100577] FATAL:  terminating connection") == "fatal"


def test_uppercase_word_later_in_message_is_not_a_level():
    line = "request to backend a b c d returned ERROR code"
    assert _explicit_level(line) is None
