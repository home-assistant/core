"""Support for Yardian integration."""

from typing import Any

import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import VolDictType

from .const import DEFAULT_WATERING_DURATION
from .coordinator import YardianConfigEntry, YardianUpdateCoordinator
from .entity import YardianZoneEntity

SERVICE_START_IRRIGATION = "start_irrigation"
SERVICE_SCHEMA_START_IRRIGATION: VolDictType = {
    vol.Required("duration"): cv.positive_int,
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: YardianConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up entry for a Yardian irrigation switches."""
    coordinator = config_entry.runtime_data
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


class YardianSwitch(YardianZoneEntity, SwitchEntity):
    """Representation of a Yardian switch."""

    _attr_translation_key = "switch"

    def __init__(self, coordinator: YardianUpdateCoordinator, zone_id: int) -> None:
        """Initialize a Yardian Switch Device."""
        super().__init__(coordinator, zone_id)
        self._attr_unique_id = f"{coordinator.yid}-{zone_id}"

    @property
    def name(self) -> str:
        """Return the zone name."""
        return self.coordinator.data.zones[self._zone_id].name

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        return self._zone_id in self.coordinator.data.active_zones

    @property
    def available(self) -> bool:
        """Return the switch is available or not."""
        return self.coordinator.data.zones[self._zone_id].is_enabled

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
