"""The power switch which can be toggled via the APsystems local API integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import DiscoveryInfoType

from . import ApSystemsConfigEntry, ApSystemsData
from .entity import ApSystemsEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ApSystemsConfigEntry,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the switch platform."""

    add_entities([ApSystemsPowerSwitch(config_entry.runtime_data)])


class ApSystemsPowerSwitch(ApSystemsEntity, SwitchEntity):
    """The switch class for APSystems switches."""

    _attr_device_class = SwitchDeviceClass.SWITCH

    def __init__(
        self,
        data: ApSystemsData,
    ) -> None:
        """Initialize the switch."""
        super().__init__(data)
        self._api = data.coordinator.api
        self._attr_unique_id = f"{data.device_id}_power_switch"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self._api.get_device_power_status() is not None

    @property
    def is_on(self) -> bool | None:
        """Return state of the switch."""
        return self._api.get_device_power_status()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.hass.async_add_executor_job(self._api.set_device_power_status(0))
        await self._api.async_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.hass.async_add_executor_job(self._api.set_device_power_status(1))
        await self._api.async_refresh()
