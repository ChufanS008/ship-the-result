#!/usr/bin/env bash
# One-line install for ship-the-result.
#
#   curl -fsSL https://raw.githubusercontent.com/ChufanS008/ship-the-result/main/install.sh | bash
#
# What it does:
#   1. clones (or updates) the skill into ~/.claude/skills/ship-the-result
#   2. merges the PreToolUse hook into ~/.claude/settings.json (backup kept, idempotent)
#   3. runs the fixture test so you can see the scanner works on your machine
#
# Uninstall: remove the hook entry from ~/.claude/settings.json and delete the skill directory.
set -euo pipefail

REPO="https://github.com/ChufanS008/ship-the-result"
CLAUDE_DIR="${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
SKILL_DIR="$CLAUDE_DIR/skills/ship-the-result"
SETTINGS="$CLAUDE_DIR/settings.json"

command -v git >/dev/null || { echo "git is required"; exit 1; }
command -v python3 >/dev/null || { echo "python3 is required"; exit 1; }

mkdir -p "$CLAUDE_DIR/skills"
if [ -d "$SKILL_DIR/.git" ]; then
  echo "updating $SKILL_DIR"
  git -C "$SKILL_DIR" pull -q --ff-only
else
  echo "cloning into $SKILL_DIR"
  git clone -q "$REPO" "$SKILL_DIR"
fi

python3 - "$SETTINGS" <<'PY'
import json, sys, shutil, pathlib, datetime
path = pathlib.Path(sys.argv[1])
cmd = 'python3 "$HOME/.claude/skills/ship-the-result/scripts/hook_pretool.py"'
entry = {"matcher": "Bash", "hooks": [{"type": "command", "command": cmd, "timeout": 15}]}

settings = {}
if path.exists():
    text = path.read_text().strip()
    if text:
        settings = json.loads(text)
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    shutil.copy(path, path.with_name(f"settings.json.bak-{stamp}"))

pre = settings.setdefault("hooks", {}).setdefault("PreToolUse", [])
already = any("ship-the-result/scripts/hook_pretool.py" in h.get("command", "")
              for e in pre for h in e.get("hooks", []))
if already:
    print(f"hook already present in {path}")
else:
    pre.append(entry)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n")
    print(f"hook added to {path}")
PY

echo
python3 "$SKILL_DIR/tests/test_residue.py" | tail -2
echo
echo "installed. Open a new Claude Code session and it is active."
echo "try it:  echo 'Update pagination per your feedback' | python3 $SKILL_DIR/scripts/residue_check.py"
