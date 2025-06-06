"""Constants for the dobiss integration."""

DOMAIN = "dobiss"
CONF_SECRET = "secret"
CONF_SECURE = "secure"

KEY_API = "dobiss_api"
DEVICES = "dobiss_devices"
DOBISS_CLIMATE_DEVICES = "dobiss_climate_devices"

# Options
CONF_INVERT_BINARY_SENSOR = "invert_binary_sensor"
DEFAULT_INVERT_BINARY_SENSOR = False
CONF_COVER_SET_END_POSITION = "send_end_position_cover"
DEFAULT_COVER_SET_END_POSITION = False
CONF_COVER_CLOSETIME = "cover_closetime"
DEFAULT_COVER_CLOSETIME = 0
CONF_COVER_USE_TIMED = "use_timed_covers"
DEFAULT_COVER_USE_TIMED = False
DEFAULT_COVER_TRAVELTIME = 55

CONF_TRAVELLING_TIME_DOWN = "travelling_time_down"
CONF_TRAVELLING_TIME_UP = "travelling_time_up"

CONF_IGNORE_ZIGBEE_DEVICES = "ignore_zigbee_devices"
DEFAULT_IGNORE_ZIGBEE_DEVICES = False

CONF_WEBSOCKET_TIMEOUT = "websocket_timeout"
DEFAULT_WEBSOCKET_TIMEOUT = 0
