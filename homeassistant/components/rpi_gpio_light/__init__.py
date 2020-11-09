"""Support for controlling a Raspberry Pi light."""
from RPi import GPIO  # pylint: disable=import-error
import voluptuous as vol

from homeassistant.const import (
    CONF_NAME,
    EVENT_HOMEASSISTANT_START,
    EVENT_HOMEASSISTANT_STOP,
)
from homeassistant.helpers import config_validation as cv, discovery

from .const import (
DOMAIN,
CONF_LIGHT,
CONF_RELAY_PIN,
CONF_LIGHT_BUTTON_PIN,
CONF_LIGHT_BUTTON_PULL_MODE,
CONF_INVERT_LIGHT_BUTTON,
CONF_INVERT_RELAY,
CONF_LIGHT_BUTTON_BOUNCETIME_MILLIS,
CONF_LIGHT_BUTTON_DOUBLE_CHECK_TIME_MILLIS,
DEFAULT_LIGHT_BUTTON_PULL_MODE,
DEFAULT_INVERT_LIGHT_BUTTON,
DEFAULT_INVERT_RELAY,
DEFAULT_LIGHT_BUTTON_BOUNCETIME_MILLIS,
DEFAULT_LIGHT_DOUBLE_CHECK_TIME_MILLIS
)

_LIGHT_SHEMA = vol.All(
    cv.ensure_list,
    [
        vol.Schema(
            {
                vol.Required(CONF_NAME): cv.string,
                vol.Required(CONF_RELAY_PIN): cv.positive_int,
                vol.Required(CONF_LIGHT_BUTTON_PIN): cv.positive_int,
            }
        )
    ],
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_LIGHT): _LIGHT_SHEMA,
                vol.Optional(
                    CONF_LIGHT_BUTTON_PULL_MODE, default=DEFAULT_LIGHT_BUTTON_PULL_MODE
                ): cv.string,
                vol.Optional(
                    CONF_LIGHT_BUTTON_BOUNCETIME_MILLIS,
                    default=DEFAULT_LIGHT_BUTTON_BOUNCETIME_MILLIS,
                ): cv.positive_int,
                vol.Optional(
                    CONF_LIGHT_BUTTON_DOUBLE_CHECK_TIME_MILLIS,
                    default=DEFAULT_LIGHT_DOUBLE_CHECK_TIME_MILLIS,
                ): cv.positive_int,
                vol.Optional(
                    CONF_INVERT_LIGHT_BUTTON, default=DEFAULT_INVERT_LIGHT_BUTTON
                ): cv.boolean,
                vol.Optional(
                    CONF_INVERT_RELAY, default=DEFAULT_INVERT_RELAY
                ): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


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
    config_domain = config[DOMAIN]
    hass.data[DOMAIN] = {
        CONF_LIGHT: [],
        CONF_LIGHT_BUTTON_PULL_MODE: config_domain.get(CONF_LIGHT_BUTTON_PULL_MODE),
        CONF_INVERT_LIGHT_BUTTON: config_domain.get(CONF_INVERT_LIGHT_BUTTON),
        CONF_INVERT_RELAY: config_domain.get(CONF_INVERT_RELAY),
        CONF_LIGHT_BUTTON_BOUNCETIME_MILLIS: config_domain.get(
            CONF_LIGHT_BUTTON_BOUNCETIME_MILLIS
        ),
        CONF_LIGHT_BUTTON_DOUBLE_CHECK_TIME_MILLIS: config_domain.get(
            CONF_LIGHT_BUTTON_DOUBLE_CHECK_TIME_MILLIS
        ),
    }
    for light in config_domain.get(CONF_LIGHT):
        hass.data[DOMAIN][CONF_LIGHT].append(
            {
                CONF_NAME: light.get(CONF_NAME),
                CONF_RELAY_PIN: light.get(CONF_RELAY_PIN),
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
