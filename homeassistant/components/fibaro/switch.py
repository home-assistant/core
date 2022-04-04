"""Support for Fibaro switches."""
from __future__ import annotations

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FIBARO_DEVICES, FibaroDevice
from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Fibaro switches."""
    async_add_entities(
        [
            FibaroSwitch(device)
            for device in hass.data[DOMAIN][entry.entry_id][FIBARO_DEVICES]["switch"]
        ],
        True,
    )


class FibaroSwitch(FibaroDevice, SwitchEntity):
    """Representation of a Fibaro Switch."""

    def __init__(self, fibaro_device):
        """Initialize the Fibaro device."""
        self._state = False
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

    def turn_on(self, **kwargs):
        """Turn device on."""
        self.call_turn_on()
        self._state = True

    def turn_off(self, **kwargs):
        """Turn device off."""
        self.call_turn_off()
        self._state = False

    @property
    def is_on(self):
        """Return true if device is on."""
        return self._state

    def update(self):
        """Update device state."""
        self._state = self.current_binary_state
