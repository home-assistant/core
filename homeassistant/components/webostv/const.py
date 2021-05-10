"""Constants used for LG webOS Smart TV."""
DOMAIN = "webostv"
PLATFORMS = ["media_player"]
DEFAULT_NAME = "LG webOS Smart TV"
DEFAULT_SOURCES = ["LiveTV", "HDMI1", "HDMI2", "HDMI1"]
ATTR_BUTTON = "button"
ATTR_COMMAND = "command"
ATTR_PAYLOAD = "payload"
ATTR_SOUND_OUTPUT = "sound_output"

CONF_ON_ACTION = "turn_on_action"
CONF_SOURCES = "sources"

SERVICE_BUTTON = "button"
SERVICE_COMMAND = "command"
SERVICE_SELECT_SOUND_OUTPUT = "select_sound_output"

LIVE_TV_APP_ID = "com.webos.app.livetv"

WEBOSTV_CONFIG_FILE = "webostv.dat"

TURN_ON_SERVICE = "service"
TURN_ON_DATA = "data"
