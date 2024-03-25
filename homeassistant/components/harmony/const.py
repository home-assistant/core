"""Constants for the Harmony component."""

from homeassistant.const import Platform

DOMAIN = "harmony"
SERVICE_SYNC = "sync"
SERVICE_CHANGE_CHANNEL = "change_channel"
PLATFORMS = [Platform.REMOTE, Platform.SELECT, Platform.SWITCH]
UNIQUE_ID = "unique_id"
ACTIVITY_POWER_OFF = "PowerOff"
HARMONY_OPTIONS_UPDATE = "harmony_options_update"
ATTR_DEVICES_LIST = "devices_list"
ATTR_LAST_ACTIVITY = "last_activity"
ATTR_ACTIVITY_STARTING = "activity_starting"
PREVIOUS_ACTIVE_ACTIVITY = "Previous Active Activity"


HARMONY_DATA = "harmony_data"
CANCEL_LISTENER = "cancel_listener"
CANCEL_STOP = "cancel_stop"
