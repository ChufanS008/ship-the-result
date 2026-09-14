#!/usr/bin/env python3
"""Scan outward-facing text for conversation residue.

"Residue" is any phrase that describes the process of arriving at the
deliverable (a rejected draft, a correction, a reviewer's feedback) rather
than the deliverable itself. Commit messages, PR titles, code comments, test
names and filenames should read as if the conversation never happened.

Usage:
    residue_check.py [--kind KIND] [--json] [FILE ...]
    echo "Add retry logic (without exponential backoff)" | residue_check.py

KIND narrows which pattern families apply:
    message   commit message / PR title / PR body / release notes (default)
    comment   code comment lines
    name      identifiers: test names, function names, filenames, titles

Exit code 0 = clean, 1 = residue found. Findings go to stdout.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict

# Each family: (family_id, why it is residue, [regexes]).
# Patterns are deliberately conservative. A false positive costs one re-read;
# a false negative costs a permanent line in git history.
FAMILIES = [
    (
        "negated-draft",
        "names something that was never a requirement, only a rejected draft",
        [
            r"\(\s*(no|without|sans|minus|non-)\s*[\w\- ]+\)",        # (no ketchup) (without lodash)
            r"\b(no|without|non)[\s\-]\w+\s+(version|variant|edition|approach|impl(ementation)?)\b",
            r"\bwithout (the|using|relying on|any)\b",
            r"\binstead of (the|using|a|an)\b",
            r"\brather than (the|using|a|an)\b",
            r"\bnot (using|use|relying on|via|with)\b",
            r"\b(dropped|removed|ditched|took out|got rid of) the (\w+ )?(approach|version|draft|attempt|idea|suggestion)\b",
            r"\bno longer (uses|using|relies|relying|calls|depends)\b",
        ],
    ),
    (
        "chat-reference",
        "points at a conversation the reader was not part of",
        [
            r"\bas (we )?discussed\b",
            r"\bas (you )?(requested|asked|suggested|mentioned|wanted|noted|pointed out)\b",
            r"\bper (your|the|our) (feedback|request|review|discussion|conversation|comment|suggestion)\b",
            r"\b(based on|after|following|addressing|incorporating|address|addresses) (your|the|reviewer'?s?|review) (feedback|review|comments?|suggestions?)\b",
            r"\byou (asked|said|mentioned|wanted|suggested|pointed out|requested)\b",
            r"\bthis time\b",
            r"\bnow (correctly|properly|actually|really|finally)\b",
            r"\bshould (now )?(work|be fixed|be correct) now\b",
        ],
    ),
    (
        "revision-marker",
        "labels the artifact as a redo of something the reader never saw",
        [
            r"\b(updated|fixed|corrected|revised|new|final|clean|proper|improved|better) (version|attempt|take|draft|pass)\b",
            r"\(\s*(fixed|updated|corrected|revised|final|v\d+|take ?\d+|attempt ?\d+)\s*\)",
            r"\b(second|third|another|new) (attempt|try|pass|go)\b",
            r"\btake ?\d\b",
            r"\bv\d+ of the\b",
            r"\bre-?(did|done|doing|written|wrote|worked) (the|this|it)\b",
        ],
    ),
    (
        "apology-or-history",
        "narrates earlier mistakes instead of describing what ships",
        [
            r"\b(sorry|oops|apologies|my (mistake|bad|error))\b",
            r"\b(previously|earlier|initially|originally|at first|before),? (i|we|it|this|the code)\b",
            r"\b(the )?(first|previous|earlier|original|initial|last) (draft|attempt|version|implementation|approach|pass)\b",
            r"\bi (had|have) (previously|earlier|initially|mistakenly|wrongly|accidentally)\b",
            r"\b(mistakenly|wrongly|accidentally|erroneously) (added|used|included|wrote|put)\b",
            r"\b(turns out|it turned out)\b",
        ],
    ),
    (
        "self-reference",
        "narrates the rule it is following; the reader does not care which skill wrote this",
        [
            r"\b(ship-the-result|no-negative-echo|no-chat-residue)\b",
            r"\b(following|per|applying|according to|as per|under) (the|this|my|our)? ?(\w+[\-\w]* )?(rule|skill|guideline|policy|convention|instruction)s?\b",
            r"\b(i|we) (will|'ll|am going to|'m going to) (only|just)? ?(write|include|keep|describe|mention)\b",
            r"\b(only|just) (the )?(final(ly)?|adopted|accepted|chosen) (result|version|approach|solution|design)\b",
            r"\b(not|without) (leav|keep|includ|mention|carry)\w* (the )?(rejected|discarded|abandoned|dropped|earlier|previous) \w+",
        ],
    ),
    (
        "identifier-residue",
        "bakes a draft's history into a name that will outlive it",
        [
            r"(?i)(^|[_\-\s.])(v\d+|fixed|final|new|old|updated|corrected|revised|clean|real|actual|good|working)(?=[_\-\s.]|$)",
            r"(?i)(^|[_\-\s.])(no|without|sans)[_\-]\w+",
            r"(?i)(^|[_\-\s.])(with)?out[_\-]\w+",
            r"(?i)_?(instead|not)_of_\w+",
        ],
    ),
]

KIND_FAMILIES = {
    "message": {"negated-draft", "chat-reference", "revision-marker", "apology-or-history", "self-reference"},
    "comment": {"negated-draft", "chat-reference", "revision-marker", "apology-or-history", "self-reference"},
    "name": {"identifier-residue", "negated-draft"},
}

COMPILED = [
    (fid, why, [re.compile(p, re.IGNORECASE) for p in pats]) for fid, why, pats in FAMILIES
]


@dataclass
class Finding:
    line_no: int
    line: str
    match: str
    family: str
    why: str


def scan_text(text: str, kind: str = "message") -> list[Finding]:
    allowed = KIND_FAMILIES.get(kind, KIND_FAMILIES["message"])
    findings: list[Finding] = []
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped:
            continue
        for fid, why, regs in COMPILED:
            if fid not in allowed:
                continue
            for rg in regs:
                m = rg.search(stripped)
                if m:
                    findings.append(Finding(i, stripped, m.group(0).strip(" _-."), fid, why))
                    break  # one hit per family per line is enough
    return findings


def format_findings(findings: list[Finding], source: str = "") -> str:
    head = f"residue found in {source}:" if source else "residue found:"
    out = [head]
    for f in findings:
        out.append(f"  L{f.line_no}: {f.line}")
        out.append(f"      -> \"{f.match}\" [{f.family}] {f.why}")
    out.append("")
    out.append(
        "Rewrite from the final result and the original requirement only. "
        "Describe what the artifact is, not how the conversation got here. "
        "If a flagged phrase is a genuine requirement (e.g. the feature really is "
        "'login without password'), keep it and re-run the same command unchanged to confirm."
    )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*", help="files to scan; reads stdin when omitted")
    ap.add_argument("--kind", choices=sorted(KIND_FAMILIES), default="message")
    ap.add_argument("--json", action="store_true", help="emit findings as JSON")
    args = ap.parse_args(argv)

    sources: list[tuple[str, str]] = []
    if args.files:
        for path in args.files:
            with open(path, encoding="utf-8", errors="replace") as fh:
                sources.append((path, fh.read()))
    else:
        sources.append(("stdin", sys.stdin.read()))

    all_findings: dict[str, list[Finding]] = {}
    for name, text in sources:
        found = scan_text(text, args.kind)
        if found:
            all_findings[name] = found

    if args.json:
        print(json.dumps({k: [asdict(f) for f in v] for k, v in all_findings.items()}, indent=2))
    else:
        for name, found in all_findings.items():
            print(format_findings(found, name))
    return 1 if all_findings else 0


if __name__ == "__main__":
    sys.exit(main())
