# iBeacon #88111 write-up

## PR description

### Summary
This change addresses `home-assistant/core#88111`, where iBeacon can keep creating new devices even when users expect discovery to be constrained.

The implemented approach adds a whitelist option for iBeacon beacon IDs. Users can explicitly allow known beacon IDs, and when the whitelist is populated, only those IDs are processed for new device/entity creation and updates.

### Why this approach
Issue comments repeatedly request an allowlist/whitelist model because the current behavior can create large amounts of unwanted devices and entities in high-traffic Bluetooth environments.

A whitelist is a direct, user-controlled mechanism that aligns with the requested behavior and avoids broad architectural changes.

### Scope
Production files changed (target):
1. `homeassistant/components/ibeacon/const.py`
2. `homeassistant/components/ibeacon/config_flow.py`
3. `homeassistant/components/ibeacon/coordinator.py`
4. `homeassistant/components/ibeacon/strings.json`

Tests updated:
1. `tests/components/ibeacon/test_config_flow.py`
2. `tests/components/ibeacon/test_coordinator.py`

### Test plan
1. Verify that an empty whitelist preserves current behavior.
2. Add allowlist entries and confirm matching beacons are tracked.
3. Confirm non-allowlisted beacons do not create new devices/entities.
4. Confirm random-MAC and unique-address paths both obey filtering.
5. Verify interaction with `Enable newly added entities` remains correct.

---

## Assignment section 9: change strategy
Our strategy was to implement a whitelist-based fix directly inside the iBeacon integration, because issue participants specifically asked for that behavior and it can be delivered in medium-sized scope. We kept the change focused on the existing integration boundaries: options flow for configuration, coordinator for runtime filtering, and strings/constants for user-facing and internal consistency. This let us avoid architecture-wide changes while still addressing the core pain point of unwanted device growth.

We split work across two implementation tracks and one documentation track. One implementer handled configuration and user-facing options flow (input validation, storage format, and localization strings), and the other implementer handled runtime filtering in coordinator logic and regression tests. The third member produced the final write-up and PR narrative, then reconciled planned impact vs. actual changed files. This reduced merge risk and kept all work aligned to the assignment's medium-size target.

## Assignment section 10: pull request link
- Original repository PR: `<PASTE PR URL>`
- Fork branch comparison URL: `<PASTE COMPARE URL>`

## Assignment section 11: impact analysis vs effective change
Our impact analysis predicted a 2-4 production-file change focused on iBeacon configuration and runtime tracking behavior. The final implementation remained within that range by concentrating changes in `const.py`, `config_flow.py`, `coordinator.py`, and `strings.json`.

Compared with the initial analysis, we narrowed scope further by avoiding broader platform or entity-model changes and solving behavior within the integration itself. The largest implementation detail that expanded slightly was test coverage, where we added specific regression cases for whitelist enforcement and settings interaction. This increased confidence without changing the production-file scope.

## Assignment section 12: pros and cons of the experience
A major advantage of this change was learning how to make a practical fix in a large real-world codebase while respecting maintainability and contributor conventions. Working from a long-running public issue with extensive user feedback also made requirements clearer than in many classroom-only tasks. It improved our ability to map user pain points into bounded engineering changes.

A downside was that coordination overhead is higher in open source projects: uncertainty around maintainer availability, evolving issue discussion, and stricter quality expectations all add friction. We also had to balance ideal design with a scope that fits course constraints. Even with that challenge, the process was valuable because it closely matched real engineering tradeoffs.
