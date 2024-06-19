"""Constants for the Firmata component."""

from typing import Final

from homeassistant.const import (
    CONF_BINARY_SENSORS,
    CONF_LIGHTS,
    CONF_SENSORS,
    CONF_SWITCHES,
    Platform,
)

CONF_ARDUINO_INSTANCE_ID = "arduino_instance_id"
CONF_ARDUINO_WAIT = "arduino_wait"
CONF_DIFFERENTIAL = "differential"
CONF_INITIAL_STATE = "initial"
CONF_NEGATE_STATE = "negate"
CONF_PINS = "pins"
CONF_PIN_MODE = "pin_mode"
PIN_MODE_ANALOG = "ANALOG"
PIN_MODE_OUTPUT = "OUTPUT"
PIN_MODE_PWM = "PWM"
PIN_MODE_INPUT = "INPUT"
PIN_MODE_PULLUP = "PULLUP"
PIN_TYPE_ANALOG: Final = 1
PIN_TYPE_DIGITAL: Final = 0
CONF_SAMPLING_INTERVAL = "sampling_interval"
CONF_SERIAL_BAUD_RATE = "serial_baud_rate"
CONF_SERIAL_PORT = "serial_port"
CONF_SLEEP_TUNE = "sleep_tune"
DOMAIN = "firmata"
FIRMATA_MANUFACTURER = "Firmata"
CONF_PLATFORM_MAP = {
    CONF_BINARY_SENSORS: Platform.BINARY_SENSOR,
    CONF_LIGHTS: Platform.LIGHT,
    CONF_SENSORS: Platform.SENSOR,
    CONF_SWITCHES: Platform.SWITCH,
}
