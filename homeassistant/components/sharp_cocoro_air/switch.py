"""Switch platform for Sharp COCORO Air."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SharpCocoroAirConfigEntry
from .coordinator import SharpCocoroAirCoordinator
from .entity import SharpCocoroAirEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SharpCocoroAirConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Sharp switch entities."""
    coordinator = entry.runtime_data
    async_add_entities(
        SharpHumidificationSwitch(coordinator, device_id)
        for device_id in coordinator.data
    )


class SharpHumidificationSwitch(SharpCocoroAirEntity, SwitchEntity):
    """Switch to toggle humidification on/off."""

    _attr_device_class = SwitchDeviceClass.SWITCH
    _attr_translation_key = "humidification"

    def __init__(
        self,
        coordinator: SharpCocoroAirCoordinator,
        device_id: str,
    ) -> None:
        """Initialize the switch entity."""
        super().__init__(coordinator, device_id)
        self._attr_unique_id = f"{device_id}_humidification"

    @property
    def is_on(self) -> bool | None:
        """Return true if humidification is on."""
        return self.device_properties.get("humidify")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on humidification."""
        if (device := self.device_data) is None:
            return
        await self.coordinator.async_set_humidify(device, True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off humidification."""
        if (device := self.device_data) is None:
            return
        await self.coordinator.async_set_humidify(device, False)
