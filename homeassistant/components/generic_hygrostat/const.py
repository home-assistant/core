"""Constants for the generic hygrostat integration."""

CONF_HUMIDIFIER = "humidifier"
CONF_SENSOR = "target_sensor"
CONF_MIN_HUMIDITY = "min_humidity"
CONF_MAX_HUMIDITY = "max_humidity"
CONF_TARGET_HUMIDITY = "target_humidity"
CONF_DEVICE_CLASS = "device_class"
CONF_MIN_DUR = "min_cycle_duration"
CONF_DRY_TOLERANCE = "dry_tolerance"
CONF_WET_TOLERANCE = "wet_tolerance"
CONF_KEEP_ALIVE = "keep_alive"
CONF_INITIAL_STATE = "initial_state"
CONF_AWAY_HUMIDITY = "away_humidity"
CONF_AWAY_FIXED = "away_fixed"
CONF_STALE_DURATION = "sensor_stale_duration"

DOMAIN = "generic_hygrostat"

DEFAULT_TOLERANCE = 3
DEFAULT_NAME = "Generic Hygrostat"
