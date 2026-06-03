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

1. **Known id** → resolve to the cached `Context` and reuse it verbatim, so
   the original `parent_id` / `user_id` (e.g. the user who pressed the button
   that triggered the sandboxed automation) survive the round-trip.
2. **Unknown id** → mint a fresh main-owned `Context` with **no fabricated
   parentage** (`parent_id=None`; `user_id` per Part C) and register it in the
   cache, so any follow-on events that chain off it resolve in step 1.

The cache is populated where main *hands a context down to the sandbox* — e.g.
when main forwards a service call or event into the sandbox, the `Context` it
used is recorded under its id, so the sandbox echoing that id back resolves to
the real thing. Bound the cache (LRU / TTL) so it can't grow without limit; a
cache miss is safe (falls to step 2), so eviction only loses parentage, never
correctness.

This **replaces** `EventMirror`'s current "fresh `Context` on every re-fire"
and folds the T2 `_resolve_context` helper into the seen-id lookup.

### Part C — reconsider the per-group system user

Decide between:
- **(c1) Drop it.** Sandbox-originated unrecognised-id contexts use
  `user_id=None` (a system/unauthenticated action — the honest shape, since no
  user authored it). Removes `async_get_or_create_sandbox_user` and the
  bridge's `_async_system_user_id`. Simplest; nothing in HA needs a sandbox to
  *be* a user.
- **(c2) Keep one shared sandbox user** (not per-group) if a stable non-null
  `user_id` is wanted for audit/logbook attribution of genuinely
  sandbox-originated actions.

**Lean (c1)** unless a concrete need for a non-null attributing user surfaces —
"the sandbox did this on nobody's behalf" is most faithfully `user_id=None`.
Confirm against logbook/recorder expectations before removing (some surfaces may
render a null user oddly).

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

## Open decision for the user

- Part C: drop the system user entirely (c1, lean) vs keep one shared sandbox
  user (c2)? Hinges on whether any audit surface wants a non-null `user_id` for
  sandbox-originated actions.
