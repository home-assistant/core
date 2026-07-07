# Plan: drop the unused sandbox token + context-id restoration

> Two related simplifications from design review (2026-06-03). The sandbox is
> **not an authenticated principal inside HA** and must **never be able to
> author a `Context`** (fabricate `parent_id` / `user_id`). Today's code carries
> an unused credential and attributes sandbox events to a per-group system user;
> both can be tightened.

## Why

- **The `--token` is dead weight.** The manager mints a per-group system-user
  access token and passes it on `--token`; the runtime stores it
  (`SandboxRuntime.token`) and **never uses it** — there is no connection back
  to main to authenticate. The code comment already says it "travels the CLI
  for forward-compat". Same reasoning as `plan-strip-auth-scopes.md`: don't
  carry an unused credential; reintroduce it (freshly designed) when the
  websocket consumer actually lands.
- **The sandbox must not invent attribution.** Only `context_id` crosses the
  wire (T2 already enforced: no `parent_id` / `user_id` on outbound frames).
  But main's handling of an inbound `context_id` is incomplete: `EventMirror`
  re-fires with a **fresh** local `Context`, dropping the original attribution
  entirely. The right model is **restore from a seen id**: main remembers the
  contexts it issued, and when the sandbox echoes one back, main re-attaches the
  *original* `parent_id` / `user_id`. The sandbox can only ever return an id
  main already minted — it cannot fabricate one with a forged parent/user.
- **The per-group system user may be unnecessary.** Its only live use is as the
  `user_id` main stamps on a freshly-minted sandbox `Context` (the T2
  `_resolve_context` path). Under the restore-from-seen-id model, an
  unrecognised id should get a context with **no** fabricated parentage —
  arguably `user_id=None` (a system/unauthenticated action), not a
  sandbox-specific user. If nothing else needs the per-group user, it goes too.

## Design

### Part A — drop the unused token

- **Manager / auth:** stop minting + passing the access token.
  `async_issue_sandbox_access_token` and the `--token` argv go away (or the
  token becomes optional / empty). Keep the issuance helper code only if Part C
  keeps the system user; otherwise remove it.
- **Runtime:** drop `SandboxRuntime.token` + the `--token` CLI arg (it is
  read but never used). The Docker entrypoint's `SANDBOX_TOKEN` env handling
  goes too.
- **Reintroduction note:** when the websocket transport lands and the sandbox
  authenticates to main, the credential is redesigned then (scopes included) —
  see the SUPERSEDED `docs/auth-scoping-decision.md`.

### Part B — context-id restoration (the real model)

Main keeps a bounded **`context_id → Context` cache** of the contexts it has
issued / observed for a sandbox (per group, or one shared map). On any inbound
sandbox message carrying a `context_id` (`state_changed`, `fire_event`, and the
result of a sandbox-originated `call_service`):

1. **Known id** (in the cache, not expired) → return the cached main-owned
   `Context` verbatim, so the original `parent_id` / `user_id` (e.g. the user
   who pressed the button that triggered the sandboxed automation) survive the
   round-trip.
2. **Unknown / expired id** → mint a **brand-new** main-owned `Context` —
   `Context(user_id=None)`, which generates its **own** fresh id on main — and
   cache it under the sandbox-supplied id so repeated echoes within the same
   operation map to one stable context. **Do NOT adopt the sandbox's id**
   (`Context(id=sandbox_context_id)` is wrong here): context ids are **ULIDs
   with an embedded millisecond timestamp, and main cannot trust the sandbox's
   clock.** A sandbox could craft a ULID to back- or forward-date an event, and
   downstream consumers (recorder/logbook ordering, etc.) read time out of the
   id — so for any id main didn't itself issue, main generates its own ULID with
   its own trusted clock. The sandbox-supplied string is used only as a **cache
   key**, never as the resulting `Context`'s identity.

The cache is **seeded where main hands a context down to the sandbox** — when
main forwards a service call into the sandbox, the real `Context` (its own,
main-issued, trusted-timestamp id) is recorded under its id, so the sandbox
echoing that id back in a derived event/state resolves to the real thing.

**Bounding — TTL, not size.** Use a **15-minute TTL** (entries expire 15 min
after insertion). Volume is naturally tiny: only contexts from main→sandbox
**service calls** are cached, and the sandbox echoes them back within the same
operation (seconds), so 15 min is generous headroom. A miss is always safe — it
falls to step 2 (a fresh main context), so expiry only loses parentage on
pathologically delayed echoes, never correctness. Lazy pruning on each resolve
(plus a periodic sweep if convenient) is enough; no count cap needed given the
TTL + low volume, though a sanity max is fine as a backstop.

This **replaces** `EventMirror`'s current "fresh `Context` on every re-fire"
and folds the T2 `_resolve_context` helper into the seen-id lookup — but note
T2's current code **adopts the sandbox id** for unknown ids (`Context(id=context_id,
…)`); Part B must change that to a fresh main-generated id per the ULID-trust
reasoning above.

### Part C — DECIDED (2026-06-03): drop the per-group system user

Sandbox-originated unrecognised-id contexts use `user_id=None` (a
system/unauthenticated action — the honest shape, since no user authored it).
Remove the per-group system user entirely:
- `async_get_or_create_sandbox_user` + `async_issue_sandbox_access_token` in
  `auth.py` (the whole helper goes away with Part A's token removal).
- The bridge's `_async_system_user_id` / cached `_system_user_id`; the
  `_resolve_context` fresh-mint path uses `user_id=None`.

There is no reason for the sandbox to *be* a user right now — nothing in HA
needs it to authenticate, and "the sandbox did this on nobody's behalf" is most
faithfully `user_id=None`. Verify against logbook/recorder rendering (a null
user should already be a normal case — automations/scripts without a user
context produce it), but do not keep the user just to avoid a null.

**Future work (not now):** a richer answer than `user_id=None` would be a
`Context` that carries a **group attribute** identifying which sandbox group
originated it — useful for audit/logbook ("this came from the `custom`
sandbox") without pretending a sandbox is a user. That needs a core `Context`
change (a new optional field) and is its own design; capture it as a follow-up
when audit attribution actually needs it.

## Touch points

```
homeassistant/components/sandbox/auth.py        (drop token issuance; maybe drop system user)
homeassistant/components/sandbox/manager.py     (drop --token argv)
homeassistant/components/sandbox/bridge.py       (context cache + _resolve_context rewrite; maybe drop _async_system_user_id)
homeassistant/components/sandbox/event_mirror?  (re-fire uses resolved context, not fresh)
sandbox/hass_client/hass_client/sandbox/__init__.py   (drop self.token)
sandbox/hass_client/hass_client/sandbox/__main__.py   (drop --token arg)
sandbox/hass_client/Dockerfile + docker-entrypoint.sh (drop SANDBOX_TOKEN)
tests/components/sandbox/test_auth.py            (update / shrink)
tests/components/sandbox/ (context restoration tests)
```

## Sequencing & risk

- **Independent of the WS transport** (T4, out of scope). This is the
  locked-down-posture cleanup that should land *before* any WS work, so the
  credential is reintroduced fresh rather than evolved from dead code.
- **Part A is mechanical + low-risk** (removing an unused field). Can ship alone.
- **Parts B + C touch freshly-shipped T2 context code** — do them together with
  good tests:
  - a user-initiated action whose context flows main → sandbox → back re-fires
    on main with the **original** `user_id` / `parent_id` (known-id restore);
  - a purely sandbox-internal event re-fires with `parent_id=None` and the
    Part-C `user_id` decision;
  - the sandbox cannot cause a forged `parent_id` / `user_id` to appear on main
    by sending an unknown or crafted `context_id` (it only ever resolves to a
    main-owned context or a fresh no-parent one).
- **Cache bounding:** assert eviction degrades to a fresh context, never an
  error.

## Decisions locked (2026-06-03)

- **Part C: drop the per-group system user** (`user_id=None` for genuinely
  sandbox-originated contexts). No current reason for the sandbox to be a user.
- **Future work, not this plan:** a `Context` with a group attribute (which
  sandbox group originated an action) is a better long-term answer than a null
  user for audit/logbook — but it needs a core `Context` field change and waits
  until audit attribution needs it.
