"""Support for Yardian integration."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DEFAULT_WATERING_DURATION, DOMAIN
from .coordinator import YardianUpdateCoordinator

SERVICE_START_IRRIGATION = "start_irrigation"
SERVICE_SCHEMA_START_IRRIGATION = {
    vol.Required("duration"): cv.positive_int,
}


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
            i,
        )
        for i in range(len(coordinator.data.zones))
    )

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_START_IRRIGATION,
        SERVICE_SCHEMA_START_IRRIGATION,
        "async_turn_on",
    )


class YardianSwitch(CoordinatorEntity[YardianUpdateCoordinator], SwitchEntity):
    """Representation of a Yardian switch."""

    _attr_icon = "mdi:water"
    _attr_has_entity_name = True

    def __init__(self, coordinator: YardianUpdateCoordinator, zone_id) -> None:
        """Initialize a Yardian Switch Device."""
        super().__init__(coordinator)
        self._zone_id = zone_id
        self._attr_unique_id = f"{coordinator.yid}-{zone_id}"
        self._attr_device_info = coordinator.device_info

    @property
    def name(self) -> str:
        """Return the zone name."""
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
        await self.coordinator.controller.start_irrigation(
            self._zone_id,
            kwargs.get("duration", DEFAULT_WATERING_DURATION),
        )
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.controller.stop_irrigation()
        await self.coordinator.async_request_refresh()
