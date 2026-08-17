from __future__ import annotations

import re


NORMALIZATION_RULES = [
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE), "<UUID>"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b"), "<TIMESTAMP>"),
    (re.compile(r"\b(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}\b"), "<IP>"),
    (re.compile(r"\b(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}\b", re.IGNORECASE), "<IPV6>"),
    (re.compile(r"(?:(?:<IP>)|(?:<IPV6>)):\d+"), lambda match: f"{match.group(0).rsplit(':', 1)[0]}:<PORT>"),
    (re.compile(r"(?<!\d):\d{2,5}\b"), ":<PORT>"),
    (re.compile(r"\b[a-f0-9]{16,}\b", re.IGNORECASE), "<ID>"),
    (re.compile(r"(?<!\w)(?:[A-Za-z]:)?[\\/][^\s:]+"), "<PATH>"),
]


def normalize_message(message: str) -> str:
    normalized = message.strip()
    for pattern, replacement in NORMALIZATION_RULES:
        if callable(replacement):
            normalized = pattern.sub(replacement, normalized)
        else:
            normalized = pattern.sub(replacement, normalized)
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized
