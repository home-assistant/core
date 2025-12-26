## Overview

Integration for Energenie Mi Home devices via the cloud REST API at
https://mihome4u.co.uk/docs. Authenticates with HTTP Basic auth, caches the API key,
and uses `/subdevices/*` endpoints to list devices and send power commands.

## Implemented

- Coordinator polls device state every 60 seconds
- API client authenticates via `/users/profile` and controls devices via
  `/subdevices/power_on`/`power_off`
- Device classification: power sockets, switches, and dimmers mapped to HA entities
- Light entities are on/off only (API exposes only `power_state`, no dimming)
- Availability detection: marks devices available when `power_state` is valid,
  ignoring the `unknown_state?` flag
- Immediate state refresh after control commands

## Known Issues

- Physical switch presses don't update API state. Only API-controlled changes are
  reflected. Physical interactions may not appear in Home Assistant.
- No brightness control: dimmable devices appear as on/off only
- Device classification uses simple `device_type` heuristics; uncommon types may
  not be recognized
- Passwords stored alongside API key (re-auth flow needed to remove)
- Only `light` platform is implemented; API includes thermostats,
  sensors, and usage data not yet supported

