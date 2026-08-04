"""Constants for agent_dvr component."""

DOMAIN = "agent_dvr"

ATTRIBUTION = "Data provided by ispyconnect.com"

# Legacy data key from before the config flow gained separate username/
# password fields: existing config entries store a fully assembled base
# URL here (which may itself embed user:pass@host for Protect API auth).
SERVER_URL = "server_url"

DEFAULT_PORT = 8090
DEFAULT_SCAN_INTERVAL = 15

ATTR_LOCATION = "location"
ATTR_GROUPS = "groups"
ATTR_PTZ_TYPE = "ptz_type"

# Device typeID values as reported by Agent DVR's getObjects.
DEVICE_TYPE_CAMERA = 2
DEVICE_TYPE_MICROPHONE = 1
