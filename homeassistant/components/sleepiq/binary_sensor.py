"""Support for SleepIQ sensors."""

from asyncsleepiq import SleepIQBed, SleepIQSleeper

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ICON_EMPTY, ICON_OCCUPIED, IS_IN_BED
from .coordinator import SleepIQConfigEntry, SleepIQDataUpdateCoordinator
from .entity import SleepIQSleeperEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SleepIQConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed binary sensors."""
    data = entry.runtime_data
    async_add_entities(
        IsInBedBinarySensor(data.data_coordinator, bed, sleeper)
        for bed in data.client.beds.values()
        for sleeper in bed.sleepers
    )


class IsInBedBinarySensor(
    SleepIQSleeperEntity[SleepIQDataUpdateCoordinator], BinarySensorEntity
):
    """Implementation of a SleepIQ presence sensor."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(
        self,
        coordinator: SleepIQDataUpdateCoordinator,
        bed: SleepIQBed,
        sleeper: SleepIQSleeper,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, bed, sleeper, IS_IN_BED)

    @callback
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
        self._attr_is_on = self.sleeper.in_bed
        self._attr_icon = ICON_OCCUPIED if self.sleeper.in_bed else ICON_EMPTY
