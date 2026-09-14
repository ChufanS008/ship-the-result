#!/usr/bin/env python3
"""Run the scanner over tests/fixtures.json and report precision / recall.

    python3 tests/test_residue.py          # summary + misses
    python3 tests/test_residue.py -v       # every case

Exits non-zero if any fixture is misclassified, so it doubles as a test.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from residue_check import scan_text  # noqa: E402


def main() -> int:
    verbose = "-v" in sys.argv
    cases = json.loads((ROOT / "tests" / "fixtures.json").read_text())["cases"]
    tp = fp = tn = fn = 0
    misses = []
    for c in cases:
        flagged = bool(scan_text(c["text"], c["kind"]))
        expected = c["residue"]
        if flagged and expected:
            tp += 1
        elif flagged and not expected:
            fp += 1
            misses.append(("FALSE POSITIVE", c))
        elif not flagged and expected:
            fn += 1
            misses.append(("MISSED", c))
        else:
            tn += 1
        if verbose:
            mark = "ok " if flagged == expected else "XX "
            print(f"{mark} [{c['kind']:7}] flagged={flagged!s:5} expected={expected!s:5}  {c['text']}")

    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    print(f"\n{len(cases)} cases  tp={tp} fp={fp} tn={tn} fn={fn}")
    print(f"precision={precision:.2f}  recall={recall:.2f}")
    for label, c in misses:
        print(f"  {label}: [{c['kind']}] {c['text']}")
    return 1 if misses else 0


if __name__ == "__main__":
    sys.exit(main())
