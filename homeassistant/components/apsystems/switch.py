"""The power switch which can be toggled via the APsystems local API integration."""

from __future__ import annotations

from typing import Any

from aiohttp.client_exceptions import ClientConnectionError

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

    add_entities([ApSystemsPowerSwitch(config_entry.runtime_data)])


class ApSystemsPowerSwitch(ApSystemsEntity, SwitchEntity):
    """The switch class for APSystems switches."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_translation_key = "power_output"

    def __init__(self, data: ApSystemsData) -> None:
        """Initialize the switch."""
        super().__init__(data)
        self._api = data.coordinator.api
        self._attr_unique_id = f"{data.device_id}_power_output"
        self._attr_is_on = None
        self._attr_available = False

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self._attr_available

    @property
    def is_on(self) -> bool | None:
        """Return state of the switch."""
        return self._attr_is_on

    async def async_update(self) -> None:
        """Update switch status and availability."""
        try:
            status = await self._api.get_device_power_status()
        except (TimeoutError, ClientConnectionError):
            self._attr_available = False
        finally:
            self._attr_available = True
            self._attr_is_on = bool(status)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self._api.set_device_power_status(0)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self._api.set_device_power_status(1)
