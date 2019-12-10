"""Constants for the Firmata component."""
import logging

LOGGER = logging.getLogger('.')

CONF_ARDUINO_WAIT = 'arduino_wait'
CONF_BINARY_SENSORS = 'binary_sensors'
CONF_HANDSHAKE = 'handshake'
CONF_INITIAL_STATE = 'initial'
CONF_NAME = 'name'
CONF_NEGATE_STATE = 'negate'
CONF_PIN = 'pin'
CONF_PINS = 'pins'
CONF_PIN_MODE = 'pin_mode'
PIN_MODE_OUTPUT = 'OUTPUT'
PIN_MODE_INPUT = 'INPUT'
PIN_MODE_PULLUP = 'PULLUP'
CONF_PORT = 'port'
CONF_REMOTE = 'remote'
CONF_SAMPLING_INTERVAL = 'sampling_interval'
CONF_SERIAL_PORT = 'serial_port'
CONF_SLEEP_TUNE = 'sleep_tune'
CONF_SWITCHES = 'switches'
DOMAIN = 'firmata'
