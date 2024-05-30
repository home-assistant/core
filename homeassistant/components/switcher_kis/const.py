"""Constants for the Switcher integration."""

DOMAIN = "switcher_kis"

DISCOVERY_TIME_SEC = 12

SIGNAL_DEVICE_ADD = "switcher_device_add"

# Services
CONF_AUTO_OFF = "auto_off"
CONF_TIMER_MINUTES = "timer_minutes"
SERVICE_SET_AUTO_OFF_NAME = "set_auto_off"
SERVICE_TURN_ON_WITH_TIMER_NAME = "turn_on_with_timer"

# Defines the maximum interval device must send an update before it marked unavailable
MAX_UPDATE_INTERVAL_SEC = 30
