"""Switch platform for Energenie Mi Home."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchDeviceClass, SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DEVICE_TYPE_POWER_SOCKET, DEVICE_TYPE_SWITCH
from .coordinator import MiHomeConfigEntry
from .entity import MiHomeEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: MiHomeConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Mi Home switch entities."""
    coordinator = config_entry.runtime_data

    # Filter for power socket and switch devices
    entities = [
        MiHomeSwitchEntity(coordinator, device_id)
        for device_id, device in coordinator.data.items()
        if device.device_type in (DEVICE_TYPE_POWER_SOCKET, DEVICE_TYPE_SWITCH)
    ]

    async_add_entities(entities)


class MiHomeSwitchEntity(MiHomeEntity, SwitchEntity):
    """Representation of a Mi Home power socket or switch."""

    _attr_device_class = SwitchDeviceClass.OUTLET
    _attr_translation_key = "switch"

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        device = self.coordinator.data.get(self.device_id)
        return device.is_on if device else False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.api.async_set_device_state(self.device_id, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.api.async_set_device_state(self.device_id, False)
        await self.coordinator.async_request_refresh()
