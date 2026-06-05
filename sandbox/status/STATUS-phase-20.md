Status: DONE

Phase 20 deletes the unwired Phase 7 sharing surface and replaces it
with a design doc. The Phase 7 plan called for `SharingConfig` on the
runtime + `SandboxGroupConfig` on the manager + `--share-states` /
`--share-entity-registry` / `--share-areas` CLI flags +
`DEFAULT_GROUP_CONFIGS` defaults so a future subscription consumer
could hang off them. The consumer never landed, so the config was
~40 LOC of dead surface across 5 files plus an entire test module
(`test_sharing_config.py`, 7 tests). Carrying unwired flags risks
readers assuming functionality that isn't there — Phase 16's
classification work already had to call this out specifically. Phase
20 removes the surface and replaces it with
`sandbox_v2/docs/design-share-states.md`, a focused design that
captures the entity_id-alignment constraint (the genuinely tricky
piece), the `share/subscribe_*` protocol shape, per-sandbox
allow-list filtering on main's send-side, and the still-open
questions (one-way vs bidirectional, read-only mirror semantics,
device + area registries as a follow-on to Phase 19, fan-out
performance). `OVERVIEW.md`, `CLAUDE.md`, `docs/FOLLOWUPS.md`, and
`generate_backlog.py`'s `dependencies-not-shared` bucket description
all repoint at the new design doc instead of just naming the
deferral. The locked-down posture — sandbox sees only its own
entities/services/events — was never really "behind" the flags; it
was the default-off behaviour of code that never existed. That stays
unchanged.

**No core HA files touched.**

Files added:
- sandbox_v2/STATUS-phase-20.md (this file)
- sandbox_v2/docs/design-share-states.md — design for the post-v2
  state-sharing consumer: goal, entity_id alignment constraint,
  `share/subscribe_*` protocol mechanism, main-side filtering,
  open questions (direction / write-through / device-area / fan-out),
  non-goals, why-now link to v1 limitation, files-it-will-touch
  preview.

Files changed:
- sandbox_v2/hass_client/hass_client/sandbox.py — drop the
  `SharingConfig` dataclass + `dataclass` import + `__all__` entry;
  drop the `sharing=` constructor param and the `self.sharing`
  assignment from `SandboxRuntime`.
- sandbox_v2/hass_client/hass_client/sandbox_v2/__main__.py — drop
  the three `--share-*` argparser entries and the `SharingConfig(...)`
  call in `SandboxRuntime(...)` construction.
- homeassistant/components/sandbox_v2/manager.py — drop the
  `SandboxGroupConfig` dataclass, `DEFAULT_GROUP_CONFIGS` map,
  `group_configs=` constructor param, `_group_configs` dict, the
  `group_config(group)` accessor, and the three `--share-*` argv
  branches in `_default_command`. Drop the matching `__all__` entries.
- sandbox_v2/hass_client/hass_client/testing/pytest_plugin.py — drop
  the `SharingConfig` import and the `sharing=` parameter from
  `async_setup_inprocess_sandbox`.
- tests/components/sandbox_v2/test_manager.py — drop the imports of
  `DEFAULT_GROUP_CONFIGS` / `SandboxGroupConfig`, the two
  `group_config` tests, and the `--share-*` argv assertions. Keep
  the token-factory test, narrowed to just assert the token + group
  end up in argv.
- sandbox_v2/hass_client/tests/test_sandbox_runtime.py — drop the
  `runtime.sharing.share_*` assertions from
  `test_runtime_starts_in_locked_down_sharing_posture`; the test
  docstring now describes the locked-down posture as a property of
  the runtime itself and links to the design doc.
- homeassistant/components/sandbox_v2/auth.py — module docstring
  bullet about `share_states=True` repointed at the new design doc.
- sandbox_v2/generate_backlog.py — `dependencies-not-shared` bucket
  description repointed at the design doc instead of CLAUDE.md's
  "Open follow-ups" line.
- sandbox_v2/OVERVIEW.md — status callout, "How v2 differs from v1"
  table row, "Three sandbox groups ship out of the box" table, the
  argv example, the `Scoped auth & opt-in data sharing` section, and
  the "Future work" bullet all updated to reference the design doc
  instead of the deleted flags.
- sandbox_v2/CLAUDE.md — "Read these first" entry for plan.md updated
  for Phase 20, new entry for `docs/design-share-states.md`, "Open
  follow-ups" share_states entry rewritten.
- sandbox_v2/docs/FOLLOWUPS.md — "Still open" share_states entry
  rewritten to point at the design doc.
- sandbox_v2/plan.md — Phase 20 ticked complete with inline summary.

Files removed:
- sandbox_v2/hass_client/tests/test_sharing_config.py — whole file
  (7 tests covering `SharingConfig` parsing, defaults, and runtime
  assignment).

Core HA files modified (review surface):
None.

Test results:
- `uv run pytest tests/components/sandbox_v2/ --no-cov -q` → 138 passed
  (down from 140; the two dropped tests are
  `test_default_group_config_posture` and
  `test_group_config_override`; `test_default_command_includes_token_and_share_flags`
  was narrowed to `test_default_command_includes_token` covering the
  surviving token-factory behaviour).
- `uv run pytest /home/paulus/dev/hass/core/sandbox_v2/hass_client/ -q`
  → 47 passed (down from 54; the seven dropped tests are the whole
  of `test_sharing_config.py`).
- `grep -rn 'SharingConfig\|SandboxGroupConfig\|share_states\|share_entity_registry\|share_areas\|--share-' sandbox_v2/hass_client/hass_client/ homeassistant/components/sandbox_v2/ tests/components/sandbox_v2/`
  → no matches.
- `uv run prek run --files <changed>` → ruff + ruff-format + mypy +
  pylint + prettier all pass. Codespell flags one pre-existing
  `reuses` on `plan.md:1278` (Phase 19 prose, not touched by this
  PR); leaving it alone since it's outside Phase 20's scope.

Things to flag for the next phase:
- The design doc is the contract for the future state-sharing
  consumer. The implementation will need: a `share` namespace
  websocket handler on main (3 subscribe commands), a sandbox-side
  consumer module, the `share/subscribe` exact-match scope added to
  `SANDBOX_TOKEN_SCOPES`, and a per-sandbox allow-list (the
  reintroduced equivalent of `SandboxGroupConfig`, but this time
  wired). Whichever phase picks this up should drive its config
  shape from real consumer needs rather than re-introducing the
  Phase 7 defaults verbatim.
- v1 removal is unaffected — Phase 17 already cleared the numeric
  gate, and Phase 20's surface deletion is independent of that. The
  remaining condition is still "v2 has shipped at least one stable
  release."
