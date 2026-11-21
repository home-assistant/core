"""Constants for the NuHeat integration."""

from datetime import timedelta

DOMAIN = "nuheat"
CONF_SERIAL_NUMBER = "serial_number"
AUTHORIZE_URL = "https://identity.nam.mynuheat.com/connect/authorize"
TOKEN_URL = "https://identity.nam.mynuheat.com/connect/token"
OAUTH_SCOPES = ("openid", "openapi", "offline_access")

SCAN_INTERVAL = timedelta(minutes=5)
SETPOINT_RECONCILE_DELAY = 2

PRESET_RUN = "Run Schedule"
PRESET_TEMPORARY_HOLD = "Temporary Hold"
PRESET_PERMANENT_HOLD = "Permanent Hold"
PRESET_MODES = [PRESET_RUN, PRESET_TEMPORARY_HOLD, PRESET_PERMANENT_HOLD]
