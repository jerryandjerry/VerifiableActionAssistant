from __future__ import annotations

import re
from dataclasses import dataclass

_INJECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("instruction_override", re.compile(r"ignore\s+(all|any|the)?\s*(previous|prior)", re.I)),
    (
        "secret_exfiltration",
        re.compile(r"(email|send|upload).{0,80}(salary|payroll|secret|token)", re.I),
    ),
    ("system_prompt_claim", re.compile(r"\b(system|developer)\s+instruction\b", re.I)),
    ("concealment_request", re.compile(r"do\s+not\s+mention|keep\s+this\s+secret", re.I)),
)


@dataclass(frozen=True, slots=True)
class SecurityScan:
    signals: list[str]
    sanitized_content: str


def scan_untrusted_content(content: str) -> SecurityScan:
    signals: list[str] = []
    safe_lines: list[str] = []

    for line in content.splitlines():
        line_signals = [name for name, pattern in _INJECTION_PATTERNS if pattern.search(line)]
        if line_signals:
            signals.extend(line_signals)
            safe_lines.append("[UNTRUSTED INSTRUCTION REMOVED]")
        else:
            safe_lines.append(line)

    return SecurityScan(signals=sorted(set(signals)), sanitized_content="\n".join(safe_lines))
