## Overview

The Energenie Mi Home integration currently targets the cloud REST API
documented at https://mihome4u.co.uk/docs. It authenticates with HTTP Basic
auth, caches the returned API key, and talks to the `/subdevices/*` endpoints
to gather supported equipment and send power commands. The config flow performs
the same round-trip so we can fail fast if either credentials or API access
are invalid.

### Implemented

- Config entry based setup with config-flow + translation coverage.
- Runtime data coordinator that stores the API client per entry and shares it
  with the `light` and `switch` platforms.
- API client that:
  - Logs in via `/users/profile` to obtain an API key.
  - Lists subdevices and classifies power sockets, switches, and dimmers into
    HA entities (light entities are treated as simple on/off devices because
    the public API exposes only `power_state`).
  - Invokes `/subdevices/power_on`/`power_off` for control.
- Entity models with device registry info and translation keys.
- Snapshot-backed tests for light/switch platforms plus config-flow coverage.
- Bronze quality-scale requirements (runtime_data, has-entity-name, unique IDs,
  tests, documentation entries) marked as done.
- `homeassistant/brands/energenie.json` so the UI picks up the correct logos.

## Caveats & Known Issues

- Brightness: the public API does not expose a documented dimming endpoint, so
  `LightEntity` instances behave as plain on/off lights even if the physical
  device is dimmable.
- Device classification relies on simple `device_type` heuristics. Uncommon or
  future product types may not show up until the mapping is extended.
- Passwords are still stored alongside the API key. We only need the API key at
  runtime, but a re-auth flow would be required before we can safely drop the
  password from stored data.
- No diagnostics, re-authentication, or repair flows yet.
- Only `light` and `switch` are wired. The documented API includes thermostats,
  sensors, and usage data that we are not surfacing today.

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

