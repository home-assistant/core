"""Support for controlling a Raspberry Pi cover."""
from time import sleep

from homeassistant.components import rpi_gpio
from homeassistant.components.cover import CoverEntity
from homeassistant.components.rpi_gpio.const import (
    CONF_COVER,
    CONF_COVER_INVERT_RELAY,
    CONF_COVER_INVERT_STATE,
    CONF_COVER_LIST,
    CONF_COVER_RELAY_PIN,
    CONF_COVER_RELAY_TIME,
    CONF_COVER_STATE_PIN,
    CONF_COVER_STATE_PULL_MODE,
    DOMAIN,
    PLATFORMS,
)
from homeassistant.const import CONF_NAME
from homeassistant.helpers.reload import setup_reload_service


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the RPi cover platform."""

    setup_reload_service(hass, DOMAIN, PLATFORMS)
    config_cover = hass.data[DOMAIN][CONF_COVER]
    relay_time = config_cover[CONF_COVER_RELAY_TIME]
    state_pull_mode = config_cover[CONF_COVER_STATE_PULL_MODE]
    invert_state = config_cover[CONF_COVER_INVERT_STATE]
    invert_relay = config_cover[CONF_COVER_INVERT_RELAY]
    covers = []
    covers_conf = config_cover[CONF_COVER_LIST]

    for cover in covers_conf:
        covers.append(
            RPiGPIOCover(
                cover[CONF_NAME],
                cover[CONF_COVER_RELAY_PIN],
                cover[CONF_COVER_STATE_PIN],
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
