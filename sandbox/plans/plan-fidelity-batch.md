# Plan: Sandbox v2 protocol-fidelity batch (#2, #4, #5, #6, #7)

> Scope = the smaller, related fidelity + ergonomics work. Transport/protobuf
> (#3) is a **separate** plan. Point 1 (lockdown) is a separate tiny PR,
> appended below for reference (decision: blanket `ALWAYS_MAIN`).
>
> Each numbered item is independently shippable as its own commit/PR. Suggested
> order: #2 → #7 → #5 → #6 → #4. Run `uv run pytest tests/components/sandbox_v2/`
> and `uv run pytest sandbox_v2/hass_client/` after each.

---

## #2 — CLI flag `--group` → `--name`

**Decision:** rename the CLI flag only; keep the internal `group` concept
(classifier, manager, bridge, store, auth user names) unchanged. No `--group`
alias — sandbox_v2 is unreleased, no back-compat owed.

**Changes**
- `sandbox_v2/hass_client/hass_client/sandbox_v2/__main__.py` — rename arg
  `--group` → `--name`; `SandboxRuntime(group=args.name)`; update help text
  (drop "group", say "Sandbox name, e.g. built-in / custom / main").
- `homeassistant/components/sandbox_v2/manager.py:_default_command` (~:549) —
  emit `"--name", group` instead of `"--group", group`.
- Update any test asserting the argv / parser (grep `--group` under
  `tests/components/sandbox_v2/` and `sandbox_v2/hass_client/tests/`).

**Risk:** trivial. Just ensure the manager + client agree on the flag name.

---

## #7 — Reconstruct `vol.Invalid` instead of mapping to `TypeError`

**Why:** the error frame carries only `error` (str) + `error_type` (class
name), so `vol.Invalid.path` and `MultipleInvalid` children are lost;
`_translate_remote_error` flattens to `TypeError`. Callers (service/flow
framework) handle real `vol.Invalid` correctly, so reconstructing it is more
faithful.

**Changes**
- **Wire (both `channel.py`):** when the raised exception is a
  `vol.Invalid`/`vol.MultipleInvalid`, add a structured `error_data` field to
  the error frame:
  - `vol.Invalid` → `{"kind": "invalid", "msg": err.error_message,
    "path": [str/​int parts]}`
  - `vol.MultipleInvalid` → `{"kind": "multiple", "errors": [<each child as
    above>]}`
  - Client emit site: `sandbox_v2/hass_client/hass_client/channel.py:266-275`.
  - Mirror the symmetric change in `homeassistant/components/sandbox_v2/channel.py`.
- **`ChannelRemoteError`** (both channels): add optional `error_data: dict |
  None = None` ctor arg + attr; populate it from the frame in `_dispatch`
  (client `:193`, plus main's reader).
- **`bridge._translate_remote_error` (`:706`):** when `error_data["kind"]` is
  `invalid`/`multiple`, rebuild `vol.Invalid(msg, path=path)` /
  `vol.MultipleInvalid([...])` and return it. Fall back to the current
  class-name mapping when `error_data` is absent (older/edge frames).

**Edge cases:** `path` parts may be `vol.Marker`s / non-JSON — stringify
parts on serialize. Keep `ServiceNotFound`/`ServiceValidationError`/
`HomeAssistantError` mappings as-is.

**Tests:** a sandbox service handler raising `vol.Invalid` with a `path`
surfaces on main as a `vol.Invalid` with the same `path` + message; a
`MultipleInvalid` round-trips its child list.

---

## #5 — Prefix proxy-entity unique_ids with the source integration domain

**Why:** all proxies register under the shared `platform_name="sandbox_v2"`
(`bridge.py:483`), so entity-registry uniqueness `(domain, "sandbox_v2",
unique_id)` collides when two integrations in one group reuse a unique_id.

**Changes**
- In `_handle_register_entity` / `entity/__init__.py:44`, set the proxy
  unique_id to `f"{source_domain}:{description.unique_id}"` where
  `source_domain = entry.domain` (look up via
  `hass.config_entries.async_get_entry(description.entry_id).domain` — already
  fetched in the handler at `:312`). Skip prefixing when `unique_id is None`.
- Pick the separator deliberately: `:` is readable and not produced by HA's
  default slug logic. Document it in `const.py`.
- **Config-entry unique_id does NOT need prefixing** — the proxy flow's handler
  is the real integration domain, so config-entry unique_id is already
  namespaced per domain. Leave `proxy_flow._apply_remote_context` as-is.

**Alternative considered:** use `entry.domain` as `platform_name` instead of
the shared `"sandbox_v2"`, which namespaces unique_ids without mangling the
string. Rejected because the user asked specifically to *prefix the unique_id*,
and a per-domain platform_name complicates `_ensure_platform`'s
`(entry_id, domain)` keying. Note it in the PR description as the road-not-taken.

**Migration:** none — sandbox_v2 is unreleased, so no persisted proxy
unique_ids to migrate. (Within a single dev instance, restart re-registers from
scratch.) Call this out so a reviewer doesn't ask for a migration.

**Tests:** two stub integrations in the same group, each registering an entity
with unique_id `"1"`, both land on main without collision and with distinct
`<domain>:1` unique_ids.

---

## #6 — Idempotent / updatable `register_entity`

**Why:** `register_entity` fires once per entity; post-registration changes to
name / icon / entity_category / device link / device_info never reach main.
Neither side listens to registry-updated events.

**Decision:** reuse `MSG_REGISTER_ENTITY` as an **upsert** (no new message).

**Client — `entity_bridge.py`**
- Add `hass.bus.async_listen(EVENT_ENTITY_REGISTRY_UPDATED, ...)`: on
  `action == "update"` for an entity in `self._registered`, re-describe and
  re-send `MSG_REGISTER_ENTITY` (carries fresh name/icon/category/capabilities/
  device_info). Ignore `create` (state-changed path already registers) and let
  `remove` ride the existing `new_state is None` unregister path (or handle
  here).
- Add `hass.bus.async_listen(EVENT_DEVICE_REGISTRY_UPDATED, ...)`: on a device
  `update`, re-send `MSG_REGISTER_ENTITY` for every tracked entity linked to
  that device so the refreshed `device_info` reaches main. (Phase 19 already
  bridges device_info at register time; this keeps it current.)
- Guard against redundant resends (e.g. compare a cheap hash of the description
  to the last sent) to avoid event storms.

**Main — `bridge._handle_register_entity`**
- If `description.sandbox_entity_id` is already in `self._entities`: **update in
  place** — refresh the existing proxy's `_attr_*` fields, re-link the device
  via `dr.async_get_or_create` (idempotent), call
  `proxy.async_write_ha_state()`. Do **not** build a new proxy or call
  `async_add_entities` again.
- Else: current create path.

**Edge cases:** capability/state-attribute changes already flow via
`state_changed` — don't double-handle. Entity registry "update" can fire for
many reasons; only resend on fields we actually mirror. Ensure ordering: an
update arriving before the initial register (race) is a no-op on main (not in
`_entities`) — acceptable, the initial register will carry current values.

**Tests:** integration updates entity name post-setup → main proxy's name
updates without a second entity appearing; device firmware_version change →
main device entry updates.

---

## #4 — Lossless `data_schema` survival through the config flow

**Why:** `data_schema` already round-trips via `voluptuous_serialize`, but
`reconstruct_schema` (`schema_bridge.py`) collapses selectors / sections /
constants to a `_passthrough` validator, and serialize failures fall back to a
schema-less form (`_has_data_schema`). The flow manager re-serializes main's
reconstructed schema for the frontend, so the lossy reconstruction is what the
user sees — selectors lose their type.

**Approach:** make `reconstruct_schema` rebuild **real** objects so
re-serialization reproduces the sandbox's original list verbatim.
- Detect `"selector" in entry` → `selector.selector(entry["selector"])`
  (rebuilds the actual `Selector`; re-serializes identically).
- Detect `entry["type"] == "expandable"` (a `data_entry_flow.section`) →
  rebuild a section with `reconstruct_schema(entry["schema"])` nested +
  `collapsed` from `expanded`.
- Keep string/int/float/bool/select precise handling.
- Preserve `default` / `description` markers (already done).

**Serialize side (`hass_client/schema_bridge.py`):** confirm selectors +
sections serialize (they do via `cv.custom_serializer`); only widen the
`except (ValueError, TypeError)` swallow if a real schema is being dropped.
Keep the `_has_data_schema` fallback for genuinely unserializable schemas but
log at warning with the schema's repr so the gap is visible.

**Tests:** a FORM whose schema uses a `SelectSelector` + a `NumberSelector`
inside a section round-trips through serialize → reconstruct → re-serialize and
equals the original serialized list (snapshot/`.ambr`). Multi-step flow keeps
each step's schema.

---

## Appendix — Point 1 (separate tiny PR): blanket `ALWAYS_MAIN`

Per decision, add to `homeassistant/components/sandbox_v2/const.py`
`ALWAYS_MAIN`, each with a one-line why:
- Broad readers: `template`, `group`, `homekit`.
- Source-entity helpers (read foreign entities): `min_max`, `statistics`,
  `trend`, `threshold`, `derivative`, `integration`, `utility_meter`, `filter`,
  `mold_indicator`, `bayesian`, `generic_thermostat`, `generic_hygrostat`,
  `switch_as_x`, `history_stats`, `proximity`.

Skip `system`-type aggregators (energy, logbook, history, recorder, zone,
google_assistant, alexa, default_config) — already routed to main by classifier
rule 1. Verify `prometheus`/`alert` (YAML-only) aren't sandboxed before adding
them. Add a classifier test asserting these domains classify to main. Keep this
out of the fidelity PRs.

## Final phase — docs up to date
End this batch with the cross-cutting docs phase (`plan-v1-removal.md` Phase D):
refresh every `--group`→`--name` mention (CLAUDE.md/OVERVIEW/README) and the
`protocol.py` / `schema_bridge` / error-handling docstrings touched by #4–#7.
Fix current-state docs; leave historical `STATUS-phase-*` records intact.
