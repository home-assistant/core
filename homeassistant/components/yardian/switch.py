"""Support for Yardian integration."""
from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import YardianUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up entry for a Yardian irrigation switches."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]
    async_add_entities(
        YardianSwitch(
            coordinator,
            config_entry.as_dict(),
            i,
        )
        for i in range(len(coordinator.data.zones))
    )


class YardianSwitch(CoordinatorEntity[YardianUpdateCoordinator], SwitchEntity):
    """Representation of a Yardian switch."""

    def __init__(self, coordinator: YardianUpdateCoordinator, config, zone_id) -> None:
        """Initialize a Yardian Switch Device."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self._zone_id = zone_id
        self._attr_icon = "mdi:water"
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{config['data']['yid']}-{zone_id}"
        self._attr_device_info = coordinator.device_info

    @property
    def name(self) -> str:
        """Return state attributes."""
        return self.coordinator.data.zones[self._zone_id][0]

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._zone_id in self.coordinator.data.active_zones

    @property
    def available(self) -> bool:
        """Return the switch is available or not."""
        return self.coordinator.data.zones[self._zone_id][1] == 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        if not self.available:
            return

        await self.coordinator.controller.start_irrigation(
            self._zone_id,
            kwargs.get(
                "duration",
                self.coordinator.getZoneDefaultWateringDuration(self._zone_id),
            ),
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.controller.stop_irrigation()
        await self.coordinator.async_request_refresh()
