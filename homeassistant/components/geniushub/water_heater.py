"""Support for Genius Hub water_heater devices."""

from typing import override

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import GeniusHubConfigEntry
from .const import GH_HEATERS, GH_STATE_TO_HA, GH_TYPE, HA_OPMODE_TO_GH
from .entity import GeniusHeatingZone


async def async_setup_entry(
    hass: HomeAssistant,
    entry: GeniusHubConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Genius Hub water heater entities."""

    coordinator = entry.runtime_data

    async_add_entities(
        GeniusWaterHeater(coordinator, z)
        for z in coordinator.client.zone_objs
        if z.data.get(GH_TYPE) in GH_HEATERS
    )


class GeniusWaterHeater(GeniusHeatingZone, WaterHeaterEntity):
    """Representation of a Genius Hub water_heater device."""

    _attr_supported_features = (
        WaterHeaterEntityFeature.TARGET_TEMPERATURE
        | WaterHeaterEntityFeature.OPERATION_MODE
    )

    def __init__(self, coordinator, zone) -> None:
        """Initialize the water_heater device."""
        super().__init__(coordinator, zone)

        self._max_temp = 80.0
        self._min_temp = 30.0

    @property
    @override
    def operation_list(self) -> list[str]:
        """Return the list of available operation modes."""
        return list(HA_OPMODE_TO_GH)

    @property
    @override
    def current_operation(self) -> str | None:
        """Return the current operation mode."""
        return GH_STATE_TO_HA[self._zone.data["mode"]]

    @override
    async def async_set_operation_mode(self, operation_mode: str) -> None:
        """Set a new operation mode for this boiler."""
        await self._zone.set_mode(HA_OPMODE_TO_GH[operation_mode])
