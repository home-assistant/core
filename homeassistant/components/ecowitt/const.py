"""Constants used by ecowitt component."""

from homeassistant.const import CONF_UNIT_SYSTEM_IMPERIAL, CONF_UNIT_SYSTEM_METRIC

PLATFORMS = ["sensor"]

TYPE_SENSOR = "sensor"
TYPE_BINARY_SENSOR = "binary_sensor"
DOMAIN = "ecowitt"
DATA_CONFIG = "config"
DATA_OPTIONS = "options"
DATA_ECOWITT = "ecowitt_listener"
DATA_STATION = "station"
DATA_PASSKEY = "PASSKEY"
DATA_STATIONTYPE = "stationtype"
DATA_FREQ = "freq"
DATA_MODEL = "model"

DEFAULT_PORT = 4199

SIGNAL_UPDATE = "ecowitt_update_{}"
SIGNAL_ADD_ENTITIES = "ecowitt_add_entities_{}_{}"
SIGNAL_REMOVE_ENTITIES = "ecowitt_remove_entities_{}_{}"
SIGNAL_NEW_SENSOR = "ecowitt_new_sensor_{}_{}"

CONF_NAME = "component_name"
CONF_UNIT_BARO = "barounit"
CONF_UNIT_WIND = "windunit"
CONF_UNIT_RAIN = "rainunit"
CONF_UNIT_WINDCHILL = "windchillunit"
CONF_UNIT_LIGHTNING = "lightningunit"

S_METRIC = 1
S_IMPERIAL = 2
S_METRIC_MS = 3

W_TYPE_NEW = "new"
W_TYPE_OLD = "old"
W_TYPE_HYBRID = "hybrid"
CONF_UNIT_SYSTEM_METRIC_MS = "metric_ms"

LEAK_DETECTED = "Leak Detected"

UNIT_OPTS = [CONF_UNIT_SYSTEM_METRIC, CONF_UNIT_SYSTEM_IMPERIAL]
WIND_OPTS = [
    CONF_UNIT_SYSTEM_METRIC,
    CONF_UNIT_SYSTEM_IMPERIAL,
    CONF_UNIT_SYSTEM_METRIC_MS,
]
WINDCHILL_OPTS = [W_TYPE_HYBRID, W_TYPE_NEW, W_TYPE_OLD]
