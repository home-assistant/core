"""Support for Fibaro switches."""
from __future__ import annotations

from typing import Any

from pyfibaro.fibaro_device import DeviceModel

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
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
            for device in hass.data[DOMAIN][entry.entry_id][FIBARO_DEVICES][
                Platform.SWITCH
            ]
        ],
        True,
    )


class FibaroSwitch(FibaroDevice, SwitchEntity):
    """Representation of a Fibaro Switch."""

    def __init__(self, fibaro_device: DeviceModel) -> None:
        """Initialize the Fibaro device."""
        super().__init__(fibaro_device)
        self.entity_id = ENTITY_ID_FORMAT.format(self.ha_id)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        self.call_turn_on()
        self._attr_is_on = True

    def turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        self.call_turn_off()
        self._attr_is_on = False

    def update(self) -> None:
        """Update device state."""
        self._attr_is_on = self.current_binary_state
