from __future__ import annotations

import re


NORMALIZATION_RULES = [
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE), "<UUID>"),
    # `[T ]+\d{1,2}` also covers MariaDB's space-padded hour: `2026-09-23  7:51:57`.
    (re.compile(r"\b\d{4}-\d{2}-\d{2}(?:T| +)\d{1,2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"), "<TIMESTAMP>"),
    # Apache: `[Sat Sep 26 18:53:26.078824 2026]`
    (re.compile(r"\b(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun) (?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) +\d{1,2} \d{1,2}:\d{2}:\d{2}(?:\.\d+)? \d{4}\b"), "<TIMESTAMP>"),
    (re.compile(r"\b\d{4}[-/]\d{2}[-/]\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b"), "<DATE>"),
    # Time of day on its own (`[8:32:18 AM]`, `10:49AM`, MariaDB's `7:51:57`),
    # before the IPv6 rule would read `18:53:26` as an address. Seconds or
    # AM/PM are required so `host:22` is left to the port rule.
    (re.compile(r"\b\d{1,2}:\d{2}:\d{2}(?:[.,]\d+)?(?:\s?[AP]M\b)?|\b\d{1,2}:\d{2}\s?[AP]M\b"), "<TIME>"),
    # Process/connection counters: Postgres/gunicorn `[115304]`, Apache
    # `pid 618:tid 618`, nginx `25#25: *10470`.
    (re.compile(r"\[\d+\]"), "[<N>]"),
    (re.compile(r"\b(pid|tid) \d+"), r"\1 <N>"),
    (re.compile(r"\b\d+#\d+:"), "<N>#<N>:"),
    (re.compile(r"\*\d+\b"), "*<N>"),
    # No \b on the left: JSON-escaped `->` is `-\u003e172.19.0.36`, where the
    # IP is glued to a word character.
    (re.compile(r"(?<![\d.])(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?!\d)"), "<IP>"),
    # Must hold at least two hex groups and not be glued to a word, so Rust/C++
    # paths like `reqwest::Error` or `hyper_util::client` are left alone.
    (re.compile(r"(?<![\w:])(?=[0-9a-f:]*[0-9a-f]:[0-9a-f:]*[0-9a-f])(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}(?![\w:])", re.IGNORECASE), "<IPV6>"),
    (re.compile(r"(?:(?:<IP>)|(?:<IPV6>)):\d+"), lambda match: f"{match.group(0).rsplit(':', 1)[0]}:<PORT>"),
    (re.compile(r"(?<!\d):\d{2,5}\b"), ":<PORT>"),
    (re.compile(r"\b[a-f0-9]{16,}\b", re.IGNORECASE), "<ID>"),
    (re.compile(r"(?<!\w)(?:[A-Za-z]:)?[\\/][^\s:]+"), "<PATH>"),
]


_ANSI_ESCAPE_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def strip_ansi(text: str) -> str:
    """Remove terminal color codes (zerolog console output from Sablier,
    Traefik...), which otherwise show up as `[2m`/`[91m` garbage in the
    report and split one recurring error into several patterns."""
    return _ANSI_ESCAPE_RE.sub("", text)


def normalize_message(message: str) -> str:
    normalized = strip_ansi(message).strip()
    for pattern, replacement in NORMALIZATION_RULES:
        if callable(replacement):
            normalized = pattern.sub(replacement, normalized)
        else:
            normalized = pattern.sub(replacement, normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized
