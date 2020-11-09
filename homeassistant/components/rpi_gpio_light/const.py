"""Consts used by rpi_light."""

DOMAIN = "rpi_gpio_light"

CONF_LIGHT = "lights"
CONF_RELAY_PIN = "relay_pin"
CONF_LIGHT_BUTTON_PIN = "light_button_pin"
CONF_LIGHT_BUTTON_PULL_MODE = "light_button_pull_mode"
CONF_INVERT_LIGHT_BUTTON = "invert_light_button"
CONF_INVERT_RELAY = "invert_relay"
CONF_LIGHT_BUTTON_BOUNCETIME_MILLIS = "light_button_bouncetime_millis"
CONF_LIGHT_BUTTON_DOUBLE_CHECK_TIME_MILLIS = "light_button_double_check_time_millis"

DEFAULT_LIGHT_BUTTON_PULL_MODE = "UP"
DEFAULT_INVERT_LIGHT_BUTTON = False
DEFAULT_INVERT_RELAY = False
DEFAULT_LIGHT_BUTTON_BOUNCETIME_MILLIS = 150
DEFAULT_LIGHT_DOUBLE_CHECK_TIME_MILLIS = 25
