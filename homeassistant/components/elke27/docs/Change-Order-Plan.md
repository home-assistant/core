Change Order Plan: Adapt elkm1 Integration into elke27 (E27 + elke27_lib)

Goal
----
Produce a working Home Assistant integration under the staging domain "elke27"
that uses elke27_lib (hub/state/events model) and supports incremental
entity/platform enablement without blocking on full feature parity.

Guiding constraints
-------------------
- Keep changes small and testable.
- First milestone is "integration loads + config flow creates entry + device is registered".
- Do not create entities until library readiness/bootstrap is complete.
- Entities must be thin: read from hub snapshot; commands via hub methods.
- Avoid M1 element abstractions entirely in the E27 path.
- Treat discovery as the primary setup path.

Milestone 0: Repo hygiene and scaffolding (compile/import only)
--------------------------------------------------------------
1) manifest.json
   - Set domain/name to elke27 (already done in your staging repo).
   - Ensure requirements/loggers match how you will supply elke27_lib.
   - Confirm config_flow is enabled.

2) const.py
   - Define DOMAIN, defaults (ports/timeouts), and integration keys used in hass.data.
   - Remove/eliminate M1-only constants imports.

Success criteria:
- Home Assistant starts without import errors.
- The integration appears in UI and can start a config flow.

Milestone 1: Define the HA-side runtime architecture (hub + state + events)
---------------------------------------------------------------------------
3) Add hub module (hub.py or coordinator.py)
   - Owns one Elke27Client instance per config entry.
   - Provides:
     - async_start() / async_stop()
     - wait_ready() or equivalent (gating)
     - snapshot accessors
     - subscribe/unsubscribe plumbing
     - hub.request_* methods for future commands
   - Stores last_error + availability state for entity availability.

4) models.py
   - Replace ELKM1Data container with Elke27Data:
     - hub reference
     - unsubscribe callbacks
     - config_entry metadata
   - Centralize hass.data[DOMAIN][entry_id] layout.

5) __init__.py (minimal setup)
   - async_setup_entry:
     - create hub and start it
     - await readiness bootstrap
     - store in hass.data
     - DO NOT forward any platforms yet (or forward only a diagnostics platform later)
   - async_unload_entry:
     - stop hub
     - clean hass.data
     - unload platforms (if any)

Success criteria:
- Config entry can be created programmatically (even before config_flow rewrite).
- Entry setup/unload does not leak tasks or subscriptions.
- No entities required yet.

Milestone 2: Config flow + discovery-first onboarding
-----------------------------------------------------
6) discovery.py
   - Replace M1 discovery with elke27_lib.discovery calls.
   - Provide results with: panel_name, mac, host, port (as hint).
   - Keep scan function side-effect free and easy to unit test.

7) config_flow.py (rewrite)
   - Step: user -> discover -> choose panel (display name; bind by mac)
   - Step: connect/validate using Elke27Client through a short-lived hub/client
     - validate "ready" and get panel_info
   - Persist config entry data:
     - mac (unique_id)
     - host/port hint
     - link keys (if created/returned)
   - Add basic error mapping:
     - cannot_connect
     - invalid_link_keys / not_linked
     - authorization_required (if encountered during validation)

Success criteria:
- User can add integration in UI.
- A discovered panel is selectable by name.
- Entry is created with MAC unique_id and validated.
- Entry setup (Milestone 1) runs after creation.

Milestone 3: Device registry + base entity model
------------------------------------------------
8) entity.py
   - Create a base Elke27Entity:
     - stores reference to hub
     - implements DeviceInfo from panel_info (MAC primary, serial secondary)
     - defines availability from hub connection state
     - defines unique_id scheme <mac>_<domain>_<index>

9) Add a minimal diagnostics platform (choose sensor.py or a dedicated diagnostics.py)
   - Create 1–3 read-only entities:
     - panel name
     - firmware/build/version
     - connection status (optional)
   - Ensure updates occur via hub event subscription.

10) __init__.py
   - Forward setup for the diagnostics platform only.

Success criteria:
- Device shows up under Devices with correct identifiers.
- Basic sensors appear and update.
- Disconnect/reconnect makes entities unavailable/available properly.

Milestone 4: Areas -> alarm_control_panel (first functional control)
--------------------------------------------------------------------
11) alarm_control_panel.py
   - Create area entities from hub snapshot.
   - Map E27 area states to HA alarm states.
   - Implement arm/disarm commands via hub methods.
   - Handle AuthorizationRequired with clear HA-facing error.

12) Hub: add area bootstrap + event handling
   - Ensure hub populates configured areas (inventory-driven).
   - Subscribe to area status events; update snapshot.

13) __init__.py
   - Forward setup for alarm_control_panel platform.

Success criteria:
- Areas appear and reflect state changes from unsolicited messages.
- Arm/disarm works and reports auth-required cleanly.

Milestone 5: Zones -> binary_sensor / sensor
--------------------------------------------
14) binary_sensor.py and sensor.py
   - Create zone entities based on configured zones.
   - Map common zone signals (open/closed/alarm/trouble/bypass).
   - Ensure state updates come from hub events.

15) Hub: add zone bootstrap + event handling

Success criteria:
- Zone entities appear with correct names/types.
- Unsolicited zone changes update HA quickly and reliably.

Milestone 6: Outputs / Lights / Thermostats
-------------------------------------------
16) switch.py
   - Outputs as switches, commands through hub.

17) light.py
   - Only if E27 has a lighting domain distinct from outputs.
   - Otherwise, defer or map as outputs.

18) climate.py
   - Thermostats, commands through hub.

19) Hub: add bootstrap + event handling per domain.

Success criteria:
- Each platform works independently and can be enabled incrementally.

Milestone 7: Services and polish
--------------------------------
20) services.py + services.yaml
   - Add only E27-valid services.
   - Ensure services call hub methods and return typed errors.

21) logbook.py (optional)
   - Map key semantic events for user-friendly history.

22) strings.json
   - Add proper copy and error translations for all flow/service errors.

Success criteria:
- UX is coherent; error messages are clear; logs are actionable.

Milestone 8: Reauth/Reconfigure + resilience
--------------------------------------------
23) config_flow.py
   - Implement reconfigure for host hint changes / rediscovery.
   - Implement reauth for authorization-required scenarios if desired.

24) Hub reconnect policy
   - On disconnect: reconnect.
   - If host fails: rediscover by MAC and retry.

Success criteria:
- Stable runtime behavior across restarts/IP changes.
- Minimal user intervention for routine network changes.

Recommended execution strategy for Codex prompts
-----------------------------------------------
- One Codex prompt per milestone or per file group (2–4 files max).
- Each prompt should include:
  - the milestone goal
  - acceptance criteria (from above)
  - “no new features outside milestone”
- Run HA startup/import checks after every milestone.
- Only add platforms after diagnostics + base entity model is stable.

End state
---------
A staging integration “elke27” that:
- onboards via E27 discovery
- persists link keys and panel identity (MAC)
- maintains a live hub with state snapshot + semantic events
- exposes HA entities for areas/zones/outputs/lights/tstats
- is structured so reconciliation into “elkm1” is mechanical later
  (same hub model, same contract, minimal drift).
