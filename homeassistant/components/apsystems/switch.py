"""The power switch which can be toggled via the APsystems local API integration."""

from __future__ import annotations

from typing import Any

from aiohttp.client_exceptions import ClientConnectionError
from APsystemsEZ1 import Status

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ApSystemsConfigEntry, ApSystemsData
from .entity import ApSystemsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ApSystemsConfigEntry,
    add_entities: AddEntitiesCallback,
) -> None:
    """Set up the switch platform."""

    add_entities([ApSystemsInverterSwitch(config_entry.runtime_data)], True)


class ApSystemsInverterSwitch(ApSystemsEntity, SwitchEntity):
    """The switch class for APSystems switches."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_translation_key = "inverter_status"

    def __init__(self, data: ApSystemsData) -> None:
        """Initialize the switch."""
        super().__init__(data)
        self._api = data.coordinator.api
        self._attr_unique_id = f"{data.device_id}_inverter_status"

    async def async_update(self) -> None:
        """Update switch status and availability."""
        try:
            status = await self._api.get_device_power_status()
        except (TimeoutError, ClientConnectionError):
            self._attr_available = False
        else:
            self._attr_available = True
            self._attr_is_on = status == Status.normal

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._api.set_device_power_status(0)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._api.set_device_power_status(1)
