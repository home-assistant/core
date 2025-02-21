"""Switch for meross_scan."""

from __future__ import annotations

from typing import Any

from meross_ha.controller.toggle import ToggleXMix

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MerossDataUpdateCoordinator
from .entity import MerossEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Meross device from a config entry."""
    coordinator = config_entry.runtime_data
    device = coordinator.device

    if not isinstance(device, ToggleXMix):
        return

    new_entities = []
    for channel in device.channels:
        entity = MerossSwitch(coordinator=coordinator, channel=channel)
        new_entities.append(entity)

    async_add_entities(new_entities)


class MerossSwitch(MerossEntity, SwitchEntity):
    """Meross Switch Device."""

    def __init__(
        self,
        coordinator: MerossDataUpdateCoordinator,
        channel: int,
    ) -> None:
        """Init Meross switch."""
        super().__init__(coordinator, channel)
        self._attr_name = str(channel)

    @property
    def is_on(self) -> bool | None:
        """Return true if switch is on."""
        return self.coordinator.device.is_on(channel=self.channel)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.device.async_turn_on(self.channel)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.device.async_turn_off(self.channel)
        self.async_write_ha_state()

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the switch."""
        await self.coordinator.device.async_toggle(channel=self.channel)
        self.async_write_ha_state()
