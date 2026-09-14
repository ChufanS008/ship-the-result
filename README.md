# ship-the-result

A Claude Code skill plus a hook that keeps chat corrections out of your commit messages, PR descriptions, comments, test names and filenames.

```
git commit -m "Add retry logic (without exponential backoff)"
```

Nobody asked for exponential backoff. The agent added it in a first draft, you said no, and now the rejection is in git history forever. The same thing happens with `(no ketchup version)`, `as discussed`, `per your feedback`, `fixed version`, `test_parser_without_regex`, `retry_v2.py`, and the especially funny one where the agent writes "following the no-residue rule" into the PR body.

The cause is an audience mismatch. The agent keeps talking to the person in the chat instead of to the person who will read the file. This skill fixes the audience and adds a regex backstop for when the prompt rule wears off.

## What is in here

`SKILL.md` is the rule, framed positively: write for the reader of the artifact, from the original requirement and the final diff only. It includes the reader test, a table of residue families, and the cases that look like residue but are real requirements.

`scripts/residue_check.py` is a scanner. Feed it text on stdin, get findings and a non-zero exit. Six pattern families: negated draft, chat reference, revision marker, apology or history, self-reference, identifier residue.

`scripts/hook_pretool.py` is a Claude Code `PreToolUse` hook. It watches `git commit`, `gh pr create|edit`, `gh release create|edit`, scans the message/title/body, and for commits also scans staged comment lines, test names and new filenames. On a hit it blocks and hands the findings back to the model. The identical command issued again passes, so a genuine `Allow login without password` gets through on the second try without any flag or env var.

`tests/fixtures.json` is 59 labelled lines, half residue, half clean. The clean half is chosen to share vocabulary with the residue half.

## Install

```bash
git clone https://github.com/ChufanS008/ship-the-result ~/.claude/skills/ship-the-result
```

Then add the hook. Merge this into `~/.claude/settings.json` (or a project's `.claude/settings.json`):

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/.claude/skills/ship-the-result/scripts/hook_pretool.py\"",
            "timeout": 15
          }
        ]
      }
    ]
  }
}
```

Python 3.9+, no dependencies.

## Use the scanner by hand

```bash
echo "Update pagination per your feedback" | python3 scripts/residue_check.py
python3 scripts/residue_check.py --kind name <<< "test_export_no_lodash"
python3 scripts/residue_check.py --kind comment src/parser.py
```

## Test

```bash
python3 tests/test_residue.py -v
```

Current result on the fixture set: precision 1.00, recall 1.00 over 59 cases. That number measures the scanner, not the model. The prompt half of the skill is judged the usual way, by whether you stop hand-editing commit messages.

## Why a hook and not just a prompt

Prompt rules load at the start of a session and fade by the time the agent actually commits. A regex does not fade. The prompt teaches the model the audience; the hook catches the model when it forgets.

## Prior art

The idea of a final-output hygiene pass for agents was first framed by the `no-negative-echo` skill by 無念. This project reframes the problem as an audience mismatch rather than negation specifically, widens the scope to all conversation residue, adds the self-reference family (the skill announcing itself in the output, which the original's users reported), and moves enforcement from prompt to hook.

## License

MIT
