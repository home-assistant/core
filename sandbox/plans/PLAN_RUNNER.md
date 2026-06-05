# Plan runner

How an orchestrator session builds one plan: spawn a fresh Claude in a
`screen` window, hand it a brief, wait for a STATUS marker, verify, push, kill
the window. One plan per session, sequentially.

## Why this shape

- **Fresh context per plan.** Each sub-session reads only its plan + the files
  it needs — no drift from the orchestrator's long history.
- **The orchestrator stays the integrator.** Sub-sessions build and commit;
  the orchestrator independently verifies (tests, greps, `git status`) and is
  the only one that pushes.
- **Plans are executed with the `phx:work` skill**, which walks the plan's
  tasks and verifies (compile/test) after each step — not freehand editing.

## Steps

### 1. Write a brief to a tempfile

The brief is the sub-session's whole instruction set: which plan to read, the
locked decisions, hard rules, build steps, the exact tests/greps to run, and —
critically — to **write a STATUS marker file LAST**.

```
/tmp/<name>-brief.md
```

Hard rules every brief repeats:
- **Execute the plan with the `phx:work` skill** — step through the plan's
  tasks with its progress tracking and per-step verify (compile/test) loop.
  This is mandatory, not ad-hoc edits; the brief must say so explicitly.
- Do **not** modify the plan file.
- Do **not** push. Commit each logical step; the orchestrator pushes.
- No `--no-verify`; pre-commit must pass.
- Write `sandbox/STATUS-<plan>.md` **last** (after the final commit) — its
  appearance is the "done" signal.

### 2. Spawn the session

Multi-line text piped to `claude-screen` does **not** land reliably (the TUI
submits mid-paste). Always pipe a **single line** pointing at the brief:

```bash
echo "Read /tmp/<name>-brief.md and follow every instruction in it exactly." \
  | ~/dev/claude-screen <name> /home/paulus/dev/hass/core
```

Use an **unambiguous full `<name>`** — `screen -p` matches by prefix, so a
later `kill` on a short name can hit the wrong window.

After ~12s, confirm the prompt was submitted (not just sitting in the input
box — an onboarding banner can eat the auto-submit):

```bash
screen -X -S claude -p <name> hardcopy /tmp/<name>-launch.dump && tail -20 /tmp/<name>-launch.dump
```

If it's idle with the prompt unsent, nudge it:

```bash
screen -X -S claude -p <name> stuff $'\r'
```

### 3. Monitor for the STATUS marker

Arm a background watcher for the marker file, plus a long fallback in case the
session hangs without writing it:

- **Monitor** (persistent, until-loop):
  `until test -f sandbox/STATUS-<plan>.md; do sleep 30; done; echo done`
- **ScheduleWakeup** fallback (~40 min): on fire, peek at the window with
  `hardcopy` and `tail` to see if it's stuck.

### 4. Verify independently

Don't trust the self-report. When STATUS appears, read it, then re-run the
load-bearing checks yourself:

```bash
uv run pytest tests/components/sandbox/ --no-cov -q
uv run pytest sandbox/hass_client/ -q
# plus the plan's specific greps / hassfest / drift guard
```

Common gotcha: a sub-session sometimes lands the code commit but **forgets the
docs/STATUS second commit** — check `git status`, and commit any leftover the
brief intended.

### 5. Push and kill

```bash
git push origin sandbox
screen -X -S claude -p <name> kill
```

Then advance to the next plan.

## Gotchas (all bit at least once)

- **Single-line file-handoff only** — multi-line stdin to `claude-screen` is
  unreliable.
- **Confirm the prompt submitted** — a first-run banner can swallow it; send
  `$'\r'` to nudge.
- **`screen -p` is prefix-match** — use full, distinct window names.
- **STATUS is written last** — its presence means done; nothing earlier does.
- **Avoid git ops in the repo while a sub-session is mid-write** — index
  contention. (`prek` stash/restore usually saves you, but don't rely on it.)
- **The orchestrator is the only pusher** — keeps one integration point and
  one verification gate.
