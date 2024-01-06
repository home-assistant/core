"""Constants for the Smartfox integration."""

DOMAIN = "smartfox"

CONF_NAME = "name"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_VERIFY = "verify"
CONF_SCHEME = "scheme"
CONF_INTEVAL = "interval"
CONF_CAR_CHARGER_ENABLED = "car_charger_enabled"
CONF_HEAT_PUMP_ENABLED = "heat_pump_enabled"
CONF_WATER_SENSORS_ENABLED = "water_sensors_enabled"
CONF_BATTERY_ENABLED = "battery_enabled"

DEFAULT_NAME = "Smartfox"
DEFAULT_PORT = 80
DEFAULT_VERIFY = False
DEFAULT_SCHEME = "http"
DEFAULT_INTERVAL = 5

RELAY_STATE_ON = "On"
RELAY_STATE_OFF = "Off"
RELAY_STATE_AUTO_ON = "Auto (ON)"
RELAY_STATE_AUTO_OFF = "Auto (OFF)"

ANALOG_STATE_AUTO = "Auto"
ANALOG_STATE_ON = "On"
ANALOG_STATE_OFF = "Off"
