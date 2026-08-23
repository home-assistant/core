"""Constants, distinct from sofar_modbus's own const (register tables)."""

DOMAIN = "sofar"
ATTR_MANUFACTURER = "Sofar Solar"

DEFAULT_NAME = "Sofar"
DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1
DEFAULT_SCAN_INTERVAL = 5
SETTINGS_SCAN_INTERVAL = 60  # matches the old slow tier's 12-cycle cadence

CONF_UNIT_ID = "unit_id"
