# Point 1 research: what breaks when `built-in` is locked down

> Deliverable for brainstorm point 1. Lockdown = a sandboxed integration sees
> only its OWN entities/states/services; **no** read of other integrations'
> states, **no** entity registry, **no** area registry.
> Verified against code 2026-05-28.

## Method & headline

- **Empirical (compat sweep): no signal.** The sweep already ran fully
  isolated — the share-states consumer was never built (Phase 7's `share_*`
  flags were inert; Phase 20 deleted them), and the in-process test plugin
  constructs `SandboxRuntime(...)` with no sharing. Recorded failures are
  `test-only` autotag/snapshot noise + 5 environmental rows; the two Phase-16
  `dependencies-not-shared` flags (azure_event_hub, atag) were re-attributed to
  mock-propagation, not lockdown. So the sweep cannot tell us real-world
  breakage — integration test suites don't exercise cross-integration reads on
  the sandbox path. **Static analysis is authoritative.**
- **Two red herrings removed by the classifier:**
  1. `integration_type == "system"` already routes to **main** (classifier
     rule 1). So **energy, logbook, history, recorder, zone, google_assistant,
     alexa, default_config** never enter a sandbox — drop them from the list.
  2. YAML-only / no-config-entry integrations: sandbox routing hooks fire on
     config-**flow** creation and config-**entry** setup. An integration with
     `config_flow: false` and no config entries sets up via `async_setup` and
     **stays on main** regardless. This likely spares **prometheus** and
     **alert** (both `config_flow: false`). *(Confirm against router.py before
     relying on it.)*

## The real breakage set: config-entry integrations classified into `built-in`

These are built-in, non-system, have a config flow (or hub config entry), and
read entities/areas they don't own. Today they classify to the `built-in`
sandbox; under lockdown they break.

### A. Source-entity helpers (read a *bounded, declared* set of foreign entities)
All `integration_type: helper` (bayesian is `service`), all `config_flow: true`.
Candidate for a **narrow opt-in** (declare source entity_ids → sandbox proxies
just those states + their registry rows) rather than ALWAYS_MAIN.

| Domain | Reads | Why it breaks |
|---|---|---|
| `min_max` | `CONF_ENTITY_IDS` sensors | min/max/mean over foreign sensors |
| `statistics` | `CONF_ENTITY_ID` | stats buffer over a foreign entity |
| `trend` | `CONF_ENTITY_ID` | gradient of foreign sensor |
| `threshold` | `CONF_ENTITY_ID` | compares foreign sensor to bounds |
| `derivative` | `CONF_SOURCE` | time-derivative of foreign sensor |
| `integration` (Riemann) | `CONF_SOURCE` | integral of foreign sensor |
| `utility_meter` | `CONF_SOURCE` | tracks a foreign energy sensor |
| `filter` | `CONF_ENTITY_ID` | filtered passthrough of foreign sensor |
| `mold_indicator` | temp+humidity source entities | computes from foreign sensors |
| `bayesian` | many `CONF_ENTITY_ID` | probability from foreign states |
| `generic_thermostat` | `CONF_SENSOR` + `CONF_HEATER` | reads foreign sensor, drives foreign switch |
| `generic_hygrostat` | `CONF_SENSOR` + `CONF_HUMIDIFIER` | same for humidity |
| `switch_as_x` | wraps a foreign `switch` (+ reads `er` for device/name) | mirrors a foreign switch; also needs registry |
| `history_stats` | `CONF_ENTITY_ID` + recorder history | needs foreign state **and** recorder → unsupported until recorder is bridged |
| `proximity` | trackers + zone via `hass.states.get` | distance of foreign trackers to a foreign zone |

### B. Broad readers (read ALL entities / registries — not narrowly scopable)
Strong **ALWAYS_MAIN** candidates.

| Domain | type | Reads | Why it breaks |
|---|---|---|---|
| `template` | helper | Jinja `states()`/`is_state()` over ANY entity at render time | unbounded foreign reads; not narrowly scopable |
| `group` | helper | member entities across domains | state/attrs derive entirely from foreign members |
| `homekit` | hub | `hass.states.async_all()` + `er` + `dr` | bridges/filters all entities, resolves names from device registry |

### C. YAML-only broad readers — likely already on main (verify)
| Domain | type | Note |
|---|---|---|
| `prometheus` | hub, no config_flow | exports metrics for every entity, labels by area; YAML-only → probably stays on main |
| `alert` | hub, no config_flow | fires on a watched foreign entity; YAML-only → probably stays on main |

## Open decision (the point-1 sub-fork)

The ~15 Category-A helpers are the crux. Two dispositions:

- **(a) All Category A + B → `ALWAYS_MAIN`.** Simple, ships now. Cost: moves
  ~17 of the most popular built-in helpers out of the sandbox, eroding the
  sandbox's value for exactly the integrations users add most.
- **(b) Narrow opt-in for Category A; `ALWAYS_MAIN` only for B (+ history_stats).**
  A helper declares its source entity_ids; the sandbox proxies just those
  states (+ registry rows). Preserves sandboxing for the helper cluster but is
  more work and overlaps the deferred `design-share-states.md` consumer (a
  *scoped, declared-allow-list* subscription rather than a group-wide share).

Recommendation to discuss: **B**, because (a) guts the helper experience and
(b)'s "declared source entity_ids" allow-list is strictly narrower (and safer)
than the group-wide share the old design proposed — it may be the right v1 of
the share consumer.

## Suggested next confirmations (cheap)
- Confirm router.py only sandboxes config-**entry** integrations (spares
  prometheus/alert). 
- Confirm which Category-A helpers expose their source entity_ids declaratively
  (config-entry `options`) vs. only via templates — that determines which can
  use the narrow opt-in vs. must be ALWAYS_MAIN.
