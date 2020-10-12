"""Support for controlling a Raspberry Pi cover."""
import logging
from time import sleep

import voluptuous as vol

from homeassistant.components import rpi_gpio
from homeassistant.components.cover import PLATFORM_SCHEMA, CoverEntity
from homeassistant.const import CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.reload import setup_reload_service

from . import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)

CONF_COVERS = "covers"
CONF_RELAY_PIN = "relay_pin"
CONF_RELAY_TIME = "relay_time"
CONF_STATE_PIN = "state_pin"
CONF_STATE_PULL_MODE = "state_pull_mode"
CONF_INVERT_STATE = "invert_state"
CONF_INVERT_RELAY = "invert_relay"

DEFAULT_RELAY_TIME = 0.2
DEFAULT_STATE_PULL_MODE = "UP"
DEFAULT_INVERT_STATE = False
DEFAULT_INVERT_RELAY = False
_COVERS_SCHEMA = vol.All(
    cv.ensure_list,
    [
        vol.Schema(
            {
                CONF_NAME: cv.string,
                CONF_RELAY_PIN: cv.positive_int,
                CONF_STATE_PIN: cv.positive_int,
            }
        )
    ],
)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_COVERS): _COVERS_SCHEMA,
        vol.Optional(CONF_STATE_PULL_MODE, default=DEFAULT_STATE_PULL_MODE): cv.string,
        vol.Optional(CONF_RELAY_TIME, default=DEFAULT_RELAY_TIME): cv.positive_int,
        vol.Optional(CONF_INVERT_STATE, default=DEFAULT_INVERT_STATE): cv.boolean,
        vol.Optional(CONF_INVERT_RELAY, default=DEFAULT_INVERT_RELAY): cv.boolean,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the RPi cover platform."""

    setup_reload_service(hass, DOMAIN, PLATFORMS)

    relay_time = config.get(CONF_RELAY_TIME)
    state_pull_mode = config.get(CONF_STATE_PULL_MODE)
    invert_state = config.get(CONF_INVERT_STATE)
    invert_relay = config.get(CONF_INVERT_RELAY)
    covers = []
    covers_conf = config.get(CONF_COVERS)

    for cover in covers_conf:
        covers.append(
            RPiGPIOCover(
                cover[CONF_NAME],
                cover[CONF_RELAY_PIN],
                cover[CONF_STATE_PIN],
                state_pull_mode,
                relay_time,
                invert_state,
                invert_relay,
            )
        )
    add_entities(covers)


class RPiGPIOCover(CoverEntity):
    """Representation of a Raspberry GPIO cover."""

    def __init__(
        self,
        name,
        relay_pin,
        state_pin,
        state_pull_mode,
        relay_time,
        invert_state,
        invert_relay,
    ):
        """Initialize the cover."""
        self._name = name
        self._state = False
        self._relay_pin = relay_pin
        self._state_pin = state_pin
        self._state_pull_mode = state_pull_mode
        self._relay_time = relay_time
        self._invert_state = invert_state
        self._invert_relay = invert_relay
        rpi_gpio.setup_output(self._relay_pin)
        rpi_gpio.setup_input(self._state_pin, self._state_pull_mode)
        rpi_gpio.write_output(self._relay_pin, 0 if self._invert_relay else 1)

    @property
    def name(self):
        """Return the name of the cover if any."""
        return self._name

    def update(self):
        """Update the state of the cover."""
        self._state = rpi_gpio.read_input(self._state_pin)

    @property
    def is_closed(self):
        """Return true if cover is closed."""
        return self._state != self._invert_state

    def _trigger(self):
        """Trigger the cover."""
        rpi_gpio.write_output(self._relay_pin, 1 if self._invert_relay else 0)
        sleep(self._relay_time)
        rpi_gpio.write_output(self._relay_pin, 0 if self._invert_relay else 1)

    def close_cover(self, **kwargs):
        """Close the cover."""
        if not self.is_closed:
            self._trigger()

    def open_cover(self, **kwargs):
        """Open the cover."""
        if self.is_closed:
            self._trigger()
