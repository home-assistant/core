"""Constants for the Switcher integration."""
from homeassistant.components.switch import ATTR_CURRENT_POWER_W

DOMAIN = "switcher_kis"

CONF_DEVICE_PASSWORD = "device_password"
CONF_PHONE_ID = "phone_id"

DATA_DEVICE = "device"

SIGNAL_SWITCHER_DEVICE_UPDATE = "switcher_device_update"

ATTR_AUTO_OFF_SET = "auto_off_set"
ATTR_ELECTRIC_CURRENT = "electric_current"
ATTR_REMAINING_TIME = "remaining_time"

CONF_AUTO_OFF = "auto_off"
CONF_TIMER_MINUTES = "timer_minutes"

DEVICE_PROPERTIES_TO_HA_ATTRIBUTES = {
    "power_consumption": ATTR_CURRENT_POWER_W,
    "electric_current": ATTR_ELECTRIC_CURRENT,
    "remaining_time": ATTR_REMAINING_TIME,
    "auto_off_set": ATTR_AUTO_OFF_SET,
}

SERVICE_SET_AUTO_OFF_NAME = "set_auto_off"
SERVICE_TURN_ON_WITH_TIMER_NAME = "turn_on_with_timer"
