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
