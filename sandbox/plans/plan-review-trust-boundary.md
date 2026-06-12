# Plan — Trust-boundary hardening (review follow-up #3)

> Source: 2026-06-12 sandbox code review, security angle (all CONFIRMED).
> Status notes go to `sandbox/status/STATUS-plan-review-trust-boundary.md`.

## Goal

Make the main side actually enforce the guarantees ARCHITECTURE §6/§10 claim
against a **compromised sandbox** (the threat model the docs explicitly adopt —
the sandbox runs untrusted HACS code). Today several gates live only *in the
sandbox* (the compromised side), and main re-fires/registers/persists whatever
arrives. This plan moves enforcement to main.

Each fix is independent — they can land as separate commits/phases — but they
share one principle: **main must re-derive trust from main-side state
(`ConfigEntry.sandbox == self.group`, the approved domains main set up), never
from a sandbox-supplied identifier.**

> The §6/§10 security-posture doc wording is reconciled in **Phase 8 of this
> plan**, once the gates below are decided.

## Success criteria

- [ ] A compromised sandbox cannot fire arbitrary core/foreign event types on
      main's bus.
- [ ] A compromised sandbox cannot register a service in a domain it doesn't own.
- [ ] A compromised sandbox cannot attach entities/devices to a config entry or
      group it doesn't own.
- [ ] A compromised sandbox cannot inject translation strings for domains it
      doesn't own.
- [ ] A compromised sandbox cannot exhaust main's disk, the context cache, or
      main's memory via channel floods.
- [ ] Each gate has an adversarial test (forged frame → rejected/clamped).
- [ ] `uv run pytest tests/components/sandbox/ --no-cov -q` green;
      `uv run prek run` clean.

## Phase 1 — Main-side `fire_event` domain gate

`_handle_fire_event` (`bridge.py:548`) calls `hass.bus.async_fire(event_type,…)`
with **no** main-side validation; the `<approved_domain>_*` filter is sandbox-only.
A compromised sandbox can fire `homeassistant_stop`, `call_service`,
`state_changed`, `automation_triggered`, foreign `zha_event`, etc.

- [ ] Enforce on main the same rule the sandbox claims to: the event name must
      start with `<domain>_` for a domain this group actually owns. Derive the
      owned-domain set from main-side state — the entries with
      `entry.sandbox == self.group` plus the domains of registered proxy entities
      — **not** from anything the sandbox sends.
- [ ] Hard-deny a deny-list of core/internal event types regardless
      (`EVENT_HOMEASSISTANT_*`, `call_service`, `state_changed`,
      `service_registered`, …) so an "owned domain" can never alias a core event.
- [ ] Reject (log + drop) anything that fails; never raise into the dispatch loop.

## Phase 2 — Main-side `register_service` ownership check

`_handle_register_service` (`bridge.py:491`) gates only on "is this
`domain.service` slot free." A compromised sandbox can squat
`persistent_notification.*` or any unclaimed `domain.service`.

- [ ] Require the service `domain` to be one this group owns (same main-side
      owned-domain derivation as Phase 1). Reject registrations for unowned
      domains.
- [ ] Keep the existing "refuse to clobber an existing handler" check (that's
      correct and protects entity-service dispatch).

## Phase 3 — Main-side entry/group ownership on `register_entity` (+ device)

`_handle_register_entity` (`bridge.py:386`) validates only
`async_get_entry(entry_id) is not None` — not `entry.sandbox == self.group`.
It then pre-creates a device via
`dr.async_get_or_create(config_entry_id=entry_id, identifiers=…, connections=…)`
with attacker-controlled identifiers → cross-integration device-registry hijack
and entity attachment to a victim entry.

- [ ] Validate `entry = async_get_entry(description.entry_id)` **and**
      `entry.sandbox == self.group`. Reject otherwise (the sandbox may only
      register entities for entries main routed to *this* group).
- [ ] Apply the same `entry.sandbox == self.group` check anywhere main trusts a
      sandbox-supplied `entry_id` (`entry_setup`/`entry_unload` replies, the
      store-server group scoping is already by-construction — confirm).
- [ ] Consider constraining `device_info.identifiers`/`connections` so a sandbox
      can't merge into a device owned by a different config entry. At minimum,
      document that the device is scoped to the (now-verified-owned) entry, and
      reject a merge whose target device already belongs to a foreign entry.

## Phase 4 — Translation cache: returned-domains ⊆ requested-custom

The provider (`translation.py:152`) splices every domain the sandbox returns via
`update(by_domain)` with no `returned ⊆ requested` check; `build_resources`
narrows by the broad requested `components` set but not by the sandbox's own
domains, so a co-requested victim domain (`hue`, `http`) gets poisoned strings.

- [ ] After the `sandbox/get_translations` reply, drop any returned domain not in
      the set this group was actually asked to resolve (the group's custom
      domains for that language). Only the intersection is overlaid.
- [ ] Add a test: sandbox returns strings for `hue` alongside its own domain →
      `hue` strings are discarded, the own-domain strings pass.

## Phase 5 — Store server quotas (`_SandboxStoreServer`)

`_validate_key` (`bridge.py:624`) blocks traversal but there's no size cap, key
count cap, total quota, or max key length; `async_save` writes unconditionally
under `.storage/sandbox/<group>/` (only the 16 MB frame cap bounds it).

- [ ] Add a **max key length** to `_validate_key` (well under `NAME_MAX`).
- [ ] Add a **per-key value size cap** and a **per-group total/byte or key-count
      quota**; reject writes over quota with a clean error frame (the sandbox's
      `Store.async_save` already tolerates a failed write path — confirm it
      degrades, doesn't crash the runtime).
- [ ] Make the limits constants with comments; pick generous-but-finite defaults
      (a real integration's `.storage` is KBs–low MBs).

## Phase 6 — Bound the two memory-exhaustion vectors

- [ ] **Context cache unbounded on resolve** (`bridge.py:378`): `_resolve_context`
      inserts a fresh `Context` per unknown `context_id` but never enforces
      `_CONTEXT_CACHE_MAX` (only `_remember_context` does). Apply the same
      `while len(contexts) > _CONTEXT_CACHE_MAX: popitem(last=False)` eviction on
      the resolve path (or factor a single `_store_context` helper used by both).
- [ ] **No read backpressure / unbounded inflight tasks** (`channel.py:540`):
      the read loop decodes every frame and `create_task`s a handler; the
      semaphore caps *running* handlers but queued tasks (each holding a decoded
      payload up to 16 MB) grow without bound under a flood. Apply backpressure:
      acquire the inflight semaphore (or check a bounded queue) **before**
      reading/dispatching the next frame, so a slow handler throttles the reader.
      **Apply to BOTH channel.py mirrors.** Coordinate with the crash-recovery plan's
      `Channel.close()` edit (same file).

## Phase 7 — Adversarial tests

- [ ] One forged-frame test per phase: malicious `fire_event` type rejected;
      `register_service` for unowned domain rejected; `register_entity` with a
      foreign `entry_id` rejected; translation reply for a foreign domain
      dropped; oversized/over-quota `store_save` rejected; context-cache eviction
      under id-flood; channel backpressure under frame-flood (reader throttles).

## Phase 8 — Reconcile the security-posture docs (do last)

The 2026-06-12 doc consolidation left `ARCHITECTURE.md` §6/§10 asserting a
malicious-sandbox model. Once this plan's gates are decided, make the docs match
shipped reality (this is the one doc task that couldn't be finished during the
doc pass because it depends on what this plan actually enforces):

- [ ] **For each gate this plan shipped** (Phases 1–6): keep the strong §6/§10
      wording and add a one-line "enforced on main in `bridge.py`/`channel.py`"
      note so the guarantee is traceable to code.
- [ ] **For any gate deferred/declined:** soften the affected §6/§10 sentences to
      the real posture ("trusted-but-buggy" vs "adversarial") and add a "Known
      trust-boundary gaps" subsection listing what's not yet enforced.
- [ ] Sanity-check: no other live doc (`README.md`, `CLAUDE.md`) overstates the
      boundary.

## Verification

```bash
uv run pytest tests/components/sandbox/ --no-cov -q
uv run pytest sandbox/hass_client/ -q
bash sandbox/proto/check_drift.sh
uv run prek run --files <changed>
```

## Risks / open questions

1. **Owned-domain derivation is the linchpin** (Phases 1–3). Define one helper —
   "domains this group owns" from `entry.sandbox == self.group` + registered
   proxy domains — and reuse it, so the three gates can't disagree. Confirm it's
   available cheaply at handler time (no async registry race).
2. **Legitimate cross-domain events?** Some integrations legitimately fire events
   named for a *platform* they provide but not their manifest domain. Audit the
   real event names a sandboxed integration emits before hard-gating, so Phase 1
   doesn't drop valid traffic. Err toward the documented `<owned_domain>_*` rule.
3. **Store quota defaults.** Too tight breaks a real integration's storage; too
   loose doesn't bound disk. Sample a few integrations' `.storage` sizes to pick
   defaults; make them overridable constants.
4. **`channel.py` mirror + the crash-recovery plan overlap** — see the simplification plan drift guard; apply both
   copies, separate commit from the crash-recovery plan's close() fix.
5. **Is the threat model actually adversarial?** If the team decides the sandbox
   is "trusted-but-buggy," some phases become belt-and-suspenders rather than
   security-critical — but they're still cheap correctness guards. Decide
   explicitly and feed the decision into Phase 8's doc wording.

## Out of scope

- Sandbox→main authenticated connection / scoped credential (ARCHITECTURE §10
  future work; the websocket transport prerequisite isn't built).
- Sandbox-side hardening (the sandbox is assumed compromised; defense is on main).
