"""Support for Yardian integration."""

from datetime import datetime
from typing import Any

import voluptuous as vol

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.typing import VolDictType

from .const import DEFAULT_WATERING_DURATION
from .coordinator import YardianConfigEntry, YardianUpdateCoordinator
from .entity import YardianZoneEntity

SERVICE_START_IRRIGATION = "start_irrigation"
SERVICE_SCHEMA_START_IRRIGATION: VolDictType = {
    vol.Required("duration"): cv.positive_int,
}

REFRESH_DELAY = 2


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

    _attr_has_entity_name = True
    _attr_icon = "mdi:toggle-switch"
    _attr_name = None

    def __init__(self, coordinator: YardianUpdateCoordinator, zone_id: int) -> None:
        """Initialize a Yardian Switch Device."""
        super().__init__(coordinator, zone_id)
        self._attr_unique_id = f"{coordinator.yid}-{zone_id}"
        self._optimistic_state: bool | None = None

    @property
    def is_on(self) -> bool:
        """Return true if switch is on."""
        if self._optimistic_state is not None:
            return self._optimistic_state
        return self._zone_id in self.coordinator.data.active_zones

    @property
    def available(self) -> bool:
        """Return the switch is available or not."""
        return (
            super().available and self.coordinator.data.zones[self._zone_id].is_enabled
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        # When fresh hardware state data arrives, clear the temporary optimistic guess
        self._optimistic_state = None
        super()._handle_coordinator_update()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        await self.coordinator.controller.start_irrigation(
            self._zone_id,
            kwargs.get("duration", DEFAULT_WATERING_DURATION),
        )
        # Instantly assume the state transitions to On to bridge the hardware delay gap
        self._optimistic_state = True
        self.async_write_ha_state()

        # Schedule the background refresh 2 seconds later
        async_call_later(self.hass, 2, self._async_delayed_refresh)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        await self.coordinator.controller.stop_zone(self._zone_id)
        # Instantly assume the state transitions to Off to bridge the hardware delay gap
        self._optimistic_state = False
        self.async_write_ha_state()

        # Schedule the background refresh 2 seconds later
        async_call_later(self.hass, REFRESH_DELAY, self._async_delayed_refresh)

    @callback
    def _async_delayed_refresh(self, _now: datetime) -> None:
        """Refresh the coordinator data after a delay."""
        self.hass.async_create_task(self.coordinator.async_request_refresh())
