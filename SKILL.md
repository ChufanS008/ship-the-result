---
name: ship-the-result
description: Write commit messages, PR titles and bodies, release notes, changelogs, code comments, test names, filenames and document titles for the reader of the artifact, not for the person in the chat. Use this whenever a deliverable is about to leave the conversation and enter project history, especially after any correction, rejected draft or change of direction mid-task. Trigger on "commit this", "open a PR", "write the changelog", "name this file/test", "add a comment explaining", "write the release notes", "summarize the change", and on any final hand-off text, even when the user did not ask for clean-up. Also run its scanner before submitting text that was drafted earlier in a long session.
---

# Ship the result

## The one rule

Write every outward-facing line as the author of the artifact, for the person who will read the artifact. That reader opens the commit, the PR, the test file, the changelog. They were not in this conversation. They never saw the first draft, the correction, or the rule you are following now.

So: describe what the thing is. Never describe how the conversation arrived at it.

## Why this needs saying

When a task includes a correction ("no ketchup", "don't use lodash", "drop the backoff"), the rejected draft is still in context and it is the most salient thing there. The model's natural move is to keep addressing the person who made the correction. That produces commit messages like `Add retry logic (without exponential backoff)` when nobody ever required backoff, comments like `// iterative, as you asked`, test names like `test_parser_without_regex`, and PR bodies that explain why an approach the team never considered is not being used.

The failure is an audience mismatch. The text is written to the user in the chat instead of to the reader of the file. Everything below is a consequence of fixing the audience.

There is a second-order version of the same failure: announcing the rule. A deliverable that says "following the ship-the-result rule, only the adopted design is described here" has smuggled the conversation back in through the front door. The reader gains nothing from knowing which guideline produced the text. Apply the rule silently.

## The reader test

Before any outward-facing line ships, ask: would this sentence make sense, and carry its full meaning, to someone reading the repository a year from now with no access to this chat?

If a phrase only makes sense relative to something that was said, tried, or rejected in the conversation, it is residue. Cut it or rewrite it from the final state.

## Surfaces to check

Anything that outlives the session:

commit subject and body, PR title and description, release notes and changelog entries, code comments and docstrings, test names and test descriptions, function, variable, file and branch names, document and section titles, README and ADR text, and the final summary you hand back to the user when it is meant to be pasted somewhere.

## What residue looks like

| Family | Residue | Rewrite from final state |
|---|---|---|
| Negated draft | `Grilled cheese (no ketchup version)` | `Grilled cheese` |
| Negated draft | `Add debounce without using lodash` | `Add debounce helper` |
| Chat reference | `Fix redirect as discussed` | `Fix redirect on expired session` |
| Chat reference | `Update pagination per your feedback` | `Use cursor tokens for pagination` |
| Revision marker | `Add CSV export (fixed version)` | `Add CSV export for order history` |
| Apology / history | `Sorry, previous commit used the wrong table` | `Rename user_tbl to users` |
| Self-reference | `Per the residue rule, only the adopted design is shown` | (delete the sentence) |
| Identifier | `test_export_no_lodash`, `retry_v2.py` | `test_export_empty_dataset`, `retry.py` |

Rejected drafts still matter. They are constraints on what you build. They are not content for what you write.

## What is not residue

A negation is fine when it describes the artifact rather than the conversation:

`Allow login without password for SSO users` is a feature. `Run tests without network access in CI` is a design property. `no longer crashes on empty input` in a changelog compares two shipped versions, which the reader can see. A comment like `# regex avoided: grammar is not regular` explains a decision to the reader in the reader's terms.

The distinction: does the sentence stand on its own for a reader who never saw the chat? If yes, keep it, even if the scanner flags it.

## Procedure

1. Draft the outward-facing text from two inputs only: the original requirement and the final diff or deliverable. Pretend the intermediate turns do not exist.
2. Run the scanner on it: `python3 <skill-dir>/scripts/residue_check.py` with the text on stdin, or `--kind name` for identifiers, `--kind comment` for comment lines. Do this yourself before `git commit` or `gh pr create`; the hook (below) is a backstop, not the primary check.
3. For every finding, apply the reader test. Rewrite if it fails. If it passes because the phrase is a genuine requirement, keep it and, when the hook blocks, re-run the identical command once to confirm.
4. Hand the text off with no preamble about how it was cleaned.

## Hook (deterministic backstop)

The scanner also runs as a Claude Code `PreToolUse` hook on the Bash tool. It inspects `git commit`, `gh pr create|edit` and `gh release create|edit` commands, scans message/title/body/notes, and for commits also scans staged comment lines, test names and new filenames. On a hit it blocks with the findings; the same command issued again unchanged passes, which is how a real requirement gets confirmed.

Install: copy the `hooks` block from `hooks/settings.example.json` into `~/.claude/settings.json` (or the project's `.claude/settings.json`) and point the path at this skill's `scripts/hook_pretool.py`.

The hook exists because prompt rules decay over a long session. By turn forty the model has forgotten this file. The regex has not.
