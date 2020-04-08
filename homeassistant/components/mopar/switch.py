"""Support for the Mopar vehicle switch."""
import logging

from homeassistant.components.mopar import DOMAIN as MOPAR_DOMAIN
from homeassistant.components.switch import SwitchDevice
from homeassistant.const import STATE_OFF, STATE_ON

_LOGGER = logging.getLogger(__name__)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Mopar Switch platform."""
    data = hass.data[MOPAR_DOMAIN]
    add_entities(
        [MoparSwitch(data, index) for index, _ in enumerate(data.vehicles)], True
    )


class MoparSwitch(SwitchDevice):
    """Representation of a Mopar switch."""

    def __init__(self, data, index):
        """Initialize the Switch."""
        self._index = index
        self._name = f"{data.get_vehicle_name(self._index)} Switch"
        self._actuate = data.actuate
        self._state = None

    @property
    def name(self):
        """Return the name of the switch."""
        return self._name

    @property
    def is_on(self):
        """Return True if the entity is on."""
        return self._state == STATE_ON

    @property
    def should_poll(self):
        """Return the polling requirement for this switch."""
        return False

    def turn_on(self, **kwargs):
        """Turn on the Mopar Vehicle."""
        if self._actuate("engine_on", self._index):
            self._state = STATE_ON

    def turn_off(self, **kwargs):
        """Turn off the Mopar Vehicle."""
        if self._actuate("engine_off", self._index):
            self._state = STATE_OFF
