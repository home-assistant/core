"""Constants for the Volkszaehler Integration."""

DOMAIN = "volkszaehler"

# Konfigurationsschlüssel
CONF_UUID = "uuid"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_NAME = "name"
CONF_FROM = "from"
CONF_TO = "to"
CONF_MONITORED_CONDITIONS = "monitored_conditions"
CONF_SCANINTERVAL = "scan_interval"

# Standardwerte
DEFAULT_HOST = "localhost"
DEFAULT_PORT = 80
DEFAULT_NAME = "Volkszaehler"
DEFAULT_MONITORED_CONDITIONS = ["average"]
DEFAULT_SCANINTERVAL = 60
MIN_SCANINTERVAL = 10

# Sensor-Keys (müssen mit sensor.py übereinstimmen)
SENSOR_KEYS = ["average", "consumption", "max", "min", "last"]
