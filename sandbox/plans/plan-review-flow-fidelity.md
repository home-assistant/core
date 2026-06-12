# Plan — Config-flow forwarding fidelity (review follow-up #5)

> Source: 2026-06-12 sandbox code review, flow/router angle (all CONFIRMED).
> Status notes go to `sandbox/status/STATUS-plan-review-flow-fidelity.md`.

## Goal

Close three correctness gaps in `SandboxFlowProxy` so a sandboxed integration's
config flow behaves exactly like a local one: entry version/options survive,
unsupported result types don't leak the sandbox-side flow, and discovery-sourced
flows don't crash. Grouped because all three live in `proxy_flow.py` and share
the marshalling layer.

## Success criteria

- [ ] A sandboxed `ConfigFlow` with `VERSION`/`MINOR_VERSION` > 1 produces a main
      entry with the correct version; no spurious migration on first setup.
- [ ] `options=` passed to `async_create_entry` in the sandbox lands on the main
      entry.
- [ ] `async_show_menu` / external-step / progress flows either work or abort
      cleanly **and** release the sandbox-side flow (no `already_in_progress`
      wedge on retry).
- [ ] Zeroconf/DHCP/other discovery-sourced flows for sandboxed integrations
      reach the sandbox without crashing in `dict_to_struct`.
- [ ] Tests per fix; `uv run pytest tests/components/sandbox/ --no-cov -q` green;
      client suite green; `uv run prek run` clean.

## Phase 1 — Carry `version` / `minor_version` / `options` on create_entry

The wire `FlowResult` carries `version`/`minor_version`/`options`
(`flow_runner.py:168-179`, proto fields present) but `_adapt_result` /
the CREATE_ENTRY branch (`proxy_flow.py:197`) reads only `data`/`title`/
`description` and calls `self.async_create_entry`, which stamps the **proxy
class** defaults `VERSION=1`/`MINOR_VERSION=1` and `options={}`
(`config_entries.py:3485-3489`). On next setup the router pushes `version=1`
back, and the sandbox-side `ConfigEntry.async_setup` runs `async_migrate` for a
freshly-created entry (corruption / failed setup); options are silently dropped.

- [ ] Confirm the sender populates these fields for CREATE_ENTRY
      (`flow_runner.py`); if `options` isn't sent, add it.
- [ ] In the proxy CREATE_ENTRY path, set the resulting flow result's
      `version`/`minor_version`/`options` from the wire result. Since
      `async_create_entry` overwrites `version` from the class attribute, the
      clean fix is to set the **proxy instance's** `VERSION`/`MINOR_VERSION` to
      the sandbox flow's values *before* calling `async_create_entry` (or build
      the `ConfigFlowResult` dict directly with the correct fields). Verify the
      framework reads instance `self.VERSION`, not the class.
- [ ] Plumb `options` into the created entry (the `async_create_entry(options=…)`
      contract).
- [ ] Test: sandboxed flow with `VERSION=2` + `options={...}` → main entry has
      `version=2`, `options` set; re-setup pushes `version=2`; no migration runs.

## Phase 2 — Don't leak the sandbox-side flow on unsupported result types

MENU / EXTERNAL_STEP / SHOW_PROGRESS set `_terminated=True` before aborting
(`proxy_flow.py:248`), which makes `async_remove` skip the `flow_abort` RPC, so
the sandbox-side flow stays in progress; if it had set a `unique_id`, retries
abort with `already_in_progress` until the sandbox restarts.

- [ ] **Preferred:** actually support `async_show_menu` — it's common and
      marshals like a form (a list of menu options). If feasible in this
      iteration, add MENU to the supported result types end-to-end (marshal +
      re-issue as `async_show_menu`). External-step/progress can stay unsupported.
- [ ] For any result type that remains unsupported: do **not** set
      `_terminated=True` before aborting — let `async_remove` still fire the
      `flow_abort` RPC so the sandbox-side flow is reaped. (Split "I aborted, flow
      is gone both sides" from "I aborted main-side only, sandbox still holds it".)
- [ ] Test: a sandboxed flow returning `async_show_menu` either renders (if
      Phase 2 adds support) or aborts AND the sandbox-side flow is removed
      (a subsequent flow with the same `unique_id` is not `already_in_progress`).

## Phase 3 — Survive discovery-sourced flow payloads

`_forward_step` (`proxy_flow.py:121`) feeds the raw flow context and first-step
payload to `dict_to_struct`; discovery flows carry non-JSON objects
(`ZeroconfServiceInfo`/`DhcpServiceInfo` dataclass as `user_input`, a
`DiscoveryKey` in `context`) → `Struct.update` raises `AttributeError`/`ValueError`
that the `except (ChannelClosedError, ChannelRemoteError)` clauses don't catch →
the discovery flow crashes unhandled. The router routes discovery-sourced flows
to the sandbox (no source filter, `router.py:68-84`).

- [ ] Normalize the flow `context` and `user_input` to JSON-safe structures
      before `dict_to_struct`: convert known discovery info dataclasses
      (`*ServiceInfo`) via their `as_dict()`/`asdict`, and drop/serialize
      non-serializable context keys (`discovery_key`, etc.). Reuse an existing
      HA-aware JSON coercion (see the simplification plan's coercer consolidation) rather than a
      bespoke walk.
- [ ] On the **sandbox side**, reconstruct the discovery info object the real
      `async_step_zeroconf`/`_dhcp`/… expects from the marshalled dict, so the
      integration's discovery step receives the right type (not a plain dict).
      Confirm which discovery sources are reachable and map each.
- [ ] Broaden the `except` in `_forward_step` to fail cleanly (abort with a
      clear reason) rather than crashing, as a backstop for an unmapped type.
- [ ] Test: a zeroconf-sourced flow for a sandboxed integration round-trips —
      the sandbox's `async_step_zeroconf` receives a usable discovery object.

## Verification

```bash
uv run pytest tests/components/sandbox/ --no-cov -q
uv run pytest sandbox/hass_client/ -q
bash sandbox/proto/check_drift.sh   # if proto FlowResult fields touched
uv run prek run --files <changed>
```

## Risks / open questions

1. **Instance vs class `VERSION`** (Phase 1): confirm the framework reads
   `self.VERSION` on the proxy instance at `async_create_entry` time; if it reads
   the class attribute, build the result dict directly instead of relying on
   instance override. Test pins the behaviour.
2. **Discovery source coverage** (Phase 3): enumerate which sources actually
   route to a sandbox (zeroconf, dhcp, ssdp, usb, bluetooth, mqtt, …) and map
   each info type both directions. Start with the common ones; backstop the rest
   with the clean-abort path so nothing crashes.
3. **MENU support scope** (Phase 2): full `async_show_menu` support is the right
   altitude but may be more than this iteration wants — the minimum bar is "don't
   leak the sandbox-side flow." Ship the leak fix regardless; gate full MENU
   support on effort.
4. **Simplification-plan coercer dependency** (Phase 3): reuse the consolidated JSON coercer
   if the simplification plan lands first; otherwise use the existing
   `json_loads(json_bytes(...))` helper and let the simplification plan dedupe later.

## Out of scope

- Subscription/push flow primitives; options-flow forwarding beyond the
  create_entry `options` field (confirm options *flows* already work — this plan
  only fixes the create_entry options value).
