#!/usr/bin/env python3
"""Claude Code PreToolUse hook for the Bash tool.

Intercepts commands that write outward-facing text into project history
(git commit, gh pr create/edit, gh release create) and scans the message,
title, body and notes for conversation residue. Also scans staged changes for
residue in comments, test names and new filenames.

Blocking behaviour: exit 2 with the findings on stderr. Claude Code feeds
stderr back to the model, which then rewrites. If the exact same command is
issued again unchanged, it passes: that is the model (or the human) confirming
the flagged phrase is a genuine requirement, not residue.

Hook input arrives as JSON on stdin: {"tool_name": "Bash", "tool_input": {"command": "..."}}
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from residue_check import scan_text, format_findings  # noqa: E402

CONFIRM_DIR = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "ship-the-result"
TRIGGERS = re.compile(r"\b(git\s+commit|gh\s+pr\s+(create|edit)|gh\s+release\s+(create|edit))\b")

# Flags whose values are outward-facing prose.
TEXT_FLAGS = ("-m", "--message", "-t", "--title", "-b", "--body", "-n", "--notes", "-F", "--body-file", "--notes-file")

COMMENT_LINE = re.compile(r"^\+\s*(#|//|/\*|\*|<!--|--|;|\"\"\"|''')")
TEST_DEF = re.compile(r"^\+\s*(def test_\w+|(it|test|describe)\s*\(\s*['\"`]|func Test\w+|fn test_\w+|@Test)")


def extract_text_args(command: str) -> list[str]:
    """Pull quoted values following message/title/body flags, plus heredoc bodies."""
    texts: list[str] = []
    # heredoc: $(cat <<'EOF' ... EOF) or <<EOF ... EOF
    for m in re.finditer(r"<<-?\s*['\"]?(\w+)['\"]?\n(.*?)\n\s*\1\b", command, re.DOTALL):
        texts.append(m.group(2))
    # flag "value" / flag 'value' / flag=value
    flag_alt = "|".join(re.escape(f) for f in TEXT_FLAGS)
    for m in re.finditer(rf"(?:{flag_alt})(?:\s+|=)(\"((?:[^\"\\]|\\.)*)\"|'([^']*)'|(\S+))", command):
        val = m.group(2) if m.group(2) is not None else (m.group(3) if m.group(3) is not None else m.group(4))
        if val and not val.startswith("-") and "$(" not in val:  # heredoc bodies were captured above
            flag = m.group(0).split()[0].split("=")[0]
            if flag in ("-F", "--body-file", "--notes-file"):
                p = Path(val)
                if p.is_file():
                    texts.append(p.read_text(encoding="utf-8", errors="replace"))
            else:
                texts.append(val.encode().decode("unicode_escape") if "\\n" in val else val)
    return texts


def staged_residue() -> list[str]:
    """Scan staged diff for residue in comments, test names and added filenames."""
    reports: list[str] = []
    try:
        diff = subprocess.run(
            ["git", "diff", "--cached", "-U0", "--no-color"], capture_output=True, text=True, timeout=10
        ).stdout
        added = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=A"], capture_output=True, text=True, timeout=10
        ).stdout
    except Exception:
        return reports

    comment_lines, name_lines = [], []
    for line in diff.splitlines():
        if COMMENT_LINE.match(line):
            comment_lines.append(line[1:].strip())
        elif TEST_DEF.match(line):
            name_lines.append(line[1:].strip())

    if comment_lines:
        f = scan_text("\n".join(comment_lines), "comment")
        if f:
            reports.append(format_findings(f, "staged comments"))
    if name_lines:
        f = scan_text("\n".join(name_lines), "name")
        if f:
            reports.append(format_findings(f, "staged test names"))
    if added.strip():
        f = scan_text("\n".join(Path(p).name for p in added.splitlines()), "name")
        if f:
            reports.append(format_findings(f, "new filenames"))
    return reports


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")
    if not command or not TRIGGERS.search(command):
        return 0

    digest = hashlib.sha256(command.encode()).hexdigest()[:16]
    CONFIRM_DIR.mkdir(parents=True, exist_ok=True)
    marker = CONFIRM_DIR / digest
    if marker.exists():
        marker.unlink(missing_ok=True)  # confirmed once, let it through
        return 0

    reports: list[str] = []
    for text in extract_text_args(command):
        found = scan_text(text, "message")
        if found:
            reports.append(format_findings(found, "commit/PR text"))
    if "git commit" in command:
        reports.extend(staged_residue())

    if not reports:
        return 0

    marker.touch()
    sys.stderr.write("[ship-the-result] blocked: outward-facing text carries conversation residue.\n\n")
    sys.stderr.write("\n\n".join(reports))
    sys.stderr.write("\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
