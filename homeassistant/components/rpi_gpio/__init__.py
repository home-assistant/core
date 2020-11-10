"""Support for controlling GPIO pins of a Raspberry Pi."""
from RPi import GPIO  # pylint: disable=import-error

from homeassistant.components.rpi_gpio.const import (
    CONF_COVER,
    CONF_COVER_INVERT_RELAY,
    CONF_COVER_INVERT_STATE,
    CONF_COVER_LIST,
    CONF_COVER_RELAY_PIN,
    CONF_COVER_RELAY_TIME,
    CONF_COVER_STATE_PIN,
    CONF_COVER_STATE_PULL_MODE,
    CONF_LIGHT,
    CONF_LIGHT_BUTTON_BOUNCETIME_MILLIS,
    CONF_LIGHT_BUTTON_DOUBLE_CHECK_TIME_MILLIS,
    CONF_LIGHT_BUTTON_PIN,
    CONF_LIGHT_BUTTON_PULL_MODE,
    CONF_LIGHT_INVERT_BUTTON,
    CONF_LIGHT_INVERT_RELAY,
    CONF_LIGHT_LIST,
    CONF_LIGHT_RELAY_PIN,
    CONF_SENSOR,
    CONF_SENSOR_BOUNCETIME,
    CONF_SENSOR_INVERT_LOGIC,
    CONF_SENSOR_PORTS,
    CONF_SENSOR_PULL_MODE,
    CONF_SWITCH,
    CONF_SWITCH_INVERT_LOGIC,
    CONF_SWITCH_PORTS,
    DOMAIN,
)
from homeassistant.components.rpi_gpio.shema import RPI_GPIO_CONFIG_SCHEMA
from homeassistant.const import (
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.helpers import discovery

CONFIG_SCHEMA = RPI_GPIO_CONFIG_SCHEMA


def setup(hass, config):
    """Set up the Raspberry PI GPIO component."""

    def cleanup_gpio(event):
        """Stuff to do before stopping."""
        GPIO.cleanup()

    def prepare_gpio(event):
        """Stuff to do when Home Assistant starts."""
        hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, cleanup_gpio)

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, prepare_gpio)
    GPIO.setmode(GPIO.BCM)

    hass.data[DOMAIN] = {}

    if CONF_SENSOR in config[DOMAIN]:
        config_sensor = config[DOMAIN][CONF_SENSOR]
        hass.data[DOMAIN][CONF_SENSOR] = {
            CONF_SENSOR_PORTS: config_sensor.get(CONF_SENSOR_PORTS),
            CONF_SENSOR_BOUNCETIME: config_sensor.get(CONF_SENSOR_BOUNCETIME),
            CONF_SENSOR_INVERT_LOGIC: config_sensor.get(CONF_SENSOR_INVERT_LOGIC),
            CONF_SENSOR_PULL_MODE: config_sensor.get(CONF_SENSOR_PULL_MODE),
        }
        discovery.load_platform(hass, "binary_sensor", DOMAIN, {}, config)

    if CONF_SWITCH in config[DOMAIN]:
        config_switch = config[DOMAIN][CONF_SWITCH]
        hass.data[DOMAIN][CONF_SWITCH] = {
            CONF_SWITCH_PORTS: config_switch.get(CONF_SWITCH_PORTS),
            CONF_SWITCH_INVERT_LOGIC: config_switch.get(CONF_SWITCH_INVERT_LOGIC),
        }
        discovery.load_platform(hass, "switch", DOMAIN, {}, config)

    if CONF_COVER in config[DOMAIN]:
        config_cover = config[DOMAIN][CONF_COVER]
        hass.data[DOMAIN][CONF_COVER] = {
            CONF_COVER_LIST: [],
            CONF_COVER_RELAY_TIME: config_cover.get(CONF_COVER_RELAY_TIME),
            CONF_COVER_STATE_PULL_MODE: config_cover.get(CONF_COVER_STATE_PULL_MODE),
            CONF_COVER_INVERT_STATE: config_cover.get(CONF_COVER_INVERT_STATE),
            CONF_COVER_INVERT_RELAY: config_cover.get(CONF_COVER_INVERT_RELAY),
        }
        for cover in config_cover.get(CONF_COVER_LIST):
            hass.data[DOMAIN][CONF_COVER][CONF_COVER_LIST].append(
                {
                    CONF_NAME: cover.get(CONF_NAME),
                    CONF_COVER_RELAY_PIN: cover.get(CONF_COVER_RELAY_PIN),
                    CONF_COVER_STATE_PIN: cover.get(CONF_COVER_STATE_PIN),
                }
            )
        discovery.load_platform(hass, "switch", DOMAIN, {}, config)

    if CONF_LIGHT in config[DOMAIN]:
        config_light = config[DOMAIN][CONF_LIGHT]
        hass.data[DOMAIN][CONF_LIGHT] = {
            CONF_LIGHT_LIST: [],
            CONF_LIGHT_BUTTON_PULL_MODE: config_light.get(CONF_LIGHT_BUTTON_PULL_MODE),
            CONF_LIGHT_INVERT_BUTTON: config_light.get(CONF_LIGHT_INVERT_BUTTON),
            CONF_LIGHT_INVERT_RELAY: config_light.get(CONF_LIGHT_INVERT_RELAY),
            CONF_LIGHT_BUTTON_BOUNCETIME_MILLIS: config_light.get(
                CONF_LIGHT_BUTTON_BOUNCETIME_MILLIS
            ),
            CONF_LIGHT_BUTTON_DOUBLE_CHECK_TIME_MILLIS: config_light.get(
                CONF_LIGHT_BUTTON_DOUBLE_CHECK_TIME_MILLIS
            ),
        }
        for light in config_light.get(CONF_LIGHT_LIST):
            hass.data[DOMAIN][CONF_LIGHT][CONF_LIGHT_LIST].append(
                {
                    CONF_NAME: light.get(CONF_NAME),
                    CONF_LIGHT_RELAY_PIN: light.get(CONF_LIGHT_RELAY_PIN),
                    CONF_LIGHT_BUTTON_PIN: light.get(CONF_LIGHT_BUTTON_PIN),
                }
            )

        discovery.load_platform(hass, "light", DOMAIN, {}, config)

    return True


def setup_output(port):
    """Set up a GPIO as output."""
    GPIO.setup(port, GPIO.OUT)


def setup_input(port, pull_mode):
    """Set up a GPIO as input."""
    GPIO.setup(port, GPIO.IN, GPIO.PUD_DOWN if pull_mode == "DOWN" else GPIO.PUD_UP)


def write_output(port, value):
    """Write a value to a GPIO."""
    GPIO.output(port, value)


def read_input(port):
    """Read a value from a GPIO."""
    return GPIO.input(port)


def edge_detect(port, event_callback, bounce):
    """Add detection for RISING and FALLING events."""
    GPIO.add_event_detect(port, GPIO.BOTH, callback=event_callback, bouncetime=bounce)


def rising_edge_detect(port, event_callback, bounce):
    """Add detection for RISING."""
    GPIO.add_event_detect(port, GPIO.RISING, callback=event_callback, bouncetime=bounce)


def falling_edge_detect(port, event_callback, bounce):
    """Add detection for FALLING."""
    GPIO.add_event_detect(
        port, GPIO.FALLING, callback=event_callback, bouncetime=bounce
    )
