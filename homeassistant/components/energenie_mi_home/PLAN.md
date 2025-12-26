## Overview

The Energenie Mi Home integration currently targets the cloud REST API
documented at https://mihome4u.co.uk/docs. It authenticates with HTTP Basic
auth, caches the returned API key, and talks to the `/subdevices/*` endpoints
to gather supported equipment and send power commands. The config flow performs
the same round-trip so we can fail fast if either credentials or API access
are invalid.

### Implemented

- **Config entry based setup** with config-flow + translation coverage.
- **Runtime data coordinator** that stores the API client per entry and shares it
  with the `light` and `switch` platforms. Polls device state every 60 seconds.
- **API client** that:
  - Logs in via `/users/profile` to obtain an API key.
  - Lists subdevices and classifies power sockets, switches, and dimmers into
    HA entities (light entities are treated as simple on/off devices because
    the public API exposes only `power_state`).
  - Invokes `/subdevices/power_on`/`power_off` for control.
  - Handles availability detection correctly (ignores `unknown_state?` flag when
    devices have valid `power_state` data).
- **Entity models** with device registry info and translation keys.
- **Error handling** with proper logging for turn on/off operations.
- **Debug logging** throughout the integration for troubleshooting.
- **Immediate state refresh** after control commands (doesn't wait for next poll).
- **Snapshot-backed tests** for light/switch platforms plus config-flow coverage.
- **Bronze quality-scale requirements** (runtime_data, has-entity-name, unique IDs,
  tests, documentation entries) marked as done.
- `homeassistant/brands/energenie.json` so the UI picks up the correct logos.

## Caveats & Known Issues

- **Physical switch behavior**: When a light switch is pressed physically (on the
  device itself), the API reported state does not change. The API only reflects
  state changes made via API commands. This means physical interactions won't be
  reflected in Home Assistant until the next polling cycle, and even then the
  state may not update if the API doesn't report the change. Users should be aware
  that the integration reflects API-controlled state, not necessarily the actual
  physical device state.
- **Brightness**: The public API does not expose a documented dimming endpoint, so
  `LightEntity` instances behave as plain on/off lights even if the physical
  device is dimmable.
- **Device classification**: Relies on simple `device_type` heuristics. Uncommon or
  future product types may not show up until the mapping is extended.
- **Password storage**: Passwords are still stored alongside the API key. We only
  need the API key at runtime, but a re-auth flow would be required before we can
  safely drop the password from stored data.
- **Availability detection**: The API returns `unknown_state?=True` for all devices,
  but this doesn't indicate actual unavailability. The integration marks devices as
  available if they have valid `power_state` data, regardless of the `unknown_state?`
  flag.
- **Limited platform support**: Only `light` and `switch` platforms are implemented.
  The documented API includes thermostats, sensors, and usage data that are not
  surfaced today.
- **No diagnostics, re-authentication, or repair flows yet**.

## Next Steps

1. **Extend device coverage**: add coordinators/entities for TRVs, sensors, and
   energy usage once we model their payloads.
2. **Re-auth flow**: implement `async_step_reauth` so users can refresh API keys
   without deleting the config entry, then migrate stored entries to drop
   `CONF_PASSWORD`.
3. **Diagnostics & repairs**: add a diagnostics handler and issue reporting per
   the quality scale Silver/Gold expectations.
4. **Error surfacing**: improve error messages when the MiHome API returns
   specific maintenance or parameter errors so users see actionable feedback.
5. **Dynamic device mapping**: consider fetching `/subdevices/show` data to map
   product metadata and expose additional sensor entities (voltage, real power,
   etc.) with proper entity categories.

