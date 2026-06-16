"""Constants for the A Better Routeplanner integration."""

DOMAIN = "abetterrouteplanner"

OAUTH2_AUTHORIZE = "https://accounts.abetterrouteplanner.com/authorize"
OAUTH2_TOKEN = "https://accounts.abetterrouteplanner.com/token"
OAUTH2_CLIENT_ID = "ha-abrp-integration"

# The ABRP OIDC discovery document advertises the scope as ``oidc`` (not the
# usual ``openid``). ``offline_access`` is required to receive a refresh token.
OAUTH2_SCOPES: list[str] = ["oidc", "profile", "email", "offline_access"]

# Partner API key issued by ABRP (Iternio) for the Home Assistant integration.
# Passed to ``aioabrp.AbrpClient`` / ``aioabrp.TelemetryStream`` as the API
# key; all endpoint/header/base-URL wiring now lives in the library.
ABRP_APP_KEY = "97b4bb90-b8f5-413b-9f28-09789a3777ed"

# Config entry key holding the list of tracked vehicle IDs.
#
# Wire and dataclass use ``int`` (the API returns int64 ``vehicle_id``), but
# this value is stored as ``list[str]`` because HA's ``SelectSelector`` only
# accepts string option values. Callers reading ``entry.data[CONF_VEHICLE_IDS]``
# must therefore round-trip through ``int(...)`` before comparing against
# ``AbrpVehicle.vehicle_id``. The conversion lives at the picker/coordinator
# boundary, not in the dataclass.
CONF_VEHICLE_IDS = "vehicle_ids"

# Wall-clock cap for the SSE pre-warm window between spawning the long-lived
# telemetry consumer and forwarding the sensor platform. The JSON seed snapshot
# can lag the live stream (e.g. ``power`` is mid-charge, present on SSE but
# null in the cached JSON), so we give the consumer a brief window to merge
# any in-flight frames before the platform decides which metric entities to
# create. Bounded so a slow / empty stream never holds setup hostage.
PREWARM_WINDOW_SECONDS = 0.5


def signal_new_metric(entry_id: str) -> str:
    """Return the dispatcher signal name for first-time metric arrivals.

    Domain-prefixed and entry-scoped so two ABRP accounts on the same HA
    instance never crosstalk metric-arrival events.
    """
    return f"{DOMAIN}_new_metric_{entry_id}"
