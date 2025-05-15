"""Support for Hydrawise sprinkler valves."""

from __future__ import annotations

from typing import Any

from pydrawise.schema import Zone

from homeassistant.components.valve import (
    ValveDeviceClass,
    ValveEntity,
    ValveEntityDescription,
    ValveEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import HydrawiseConfigEntry
from .entity import HydrawiseEntity

VALVE_TYPES: tuple[ValveEntityDescription, ...] = (
    ValveEntityDescription(
        key="zone",
        device_class=ValveDeviceClass.WATER,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: HydrawiseConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Hydrawise valve platform."""
    coordinators = config_entry.runtime_data
    async_add_entities(
        HydrawiseValve(coordinators.main, description, controller, zone_id=zone.id)
        for controller in coordinators.main.data.controllers.values()
        for zone in controller.zones
        for description in VALVE_TYPES
    )


class HydrawiseValve(HydrawiseEntity, ValveEntity):
    """A Hydrawise valve."""

    _attr_name = None
    _attr_reports_position = False
    _attr_supported_features = ValveEntityFeature.OPEN | ValveEntityFeature.CLOSE
    zone: Zone

    async def async_open_valve(self, **kwargs: Any) -> None:
        """Open the valve."""
        await self.coordinator.api.start_zone(self.zone)

    async def async_close_valve(self) -> None:
        """Close the valve."""
        await self.coordinator.api.stop_zone(self.zone)

    def _update_attrs(self) -> None:
        """Update state attributes."""
        self._attr_is_closed = self.zone.scheduled_runs.current_run is None
