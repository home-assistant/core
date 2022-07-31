"""Support for Vera switches."""
from __future__ import annotations

from typing import Any

import pyvera as veraApi

from homeassistant.components.switch import ENTITY_ID_FORMAT, SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import VeraDevice
from .common import ControllerData, get_controller_data


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the sensor config entry."""
    controller_data = get_controller_data(hass, entry)
    async_add_entities(
        [
            VeraSwitch(device, controller_data)
            for device in controller_data.devices[Platform.SWITCH]
        ],
        True,
    )


class VeraSwitch(VeraDevice[veraApi.VeraSwitch], SwitchEntity):
    """Representation of a Vera Switch."""

    def __init__(
        self, vera_device: veraApi.VeraSwitch, controller_data: ControllerData
    ) -> None:
        """Initialize the Vera device."""
        self._state = False
        VeraDevice.__init__(self, vera_device, controller_data)
        self.entity_id = ENTITY_ID_FORMAT.format(self.vera_id)

    def turn_on(self, **kwargs: Any) -> None:
        """Turn device on."""
        self.vera_device.switch_on()
        self._state = True
        self.schedule_update_ha_state()

    def turn_off(self, **kwargs: Any) -> None:
        """Turn device off."""
        self.vera_device.switch_off()
        self._state = False
        self.schedule_update_ha_state()

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._state

    def update(self) -> None:
        """Update device state."""
        super().update()
        self._state = self.vera_device.is_switched_on()
