"""Support for SleepIQ sensors."""
from asyncsleepiq import SleepIQBed, SleepIQSleeper

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, ICON_EMPTY, ICON_OCCUPIED, IS_IN_BED
from .coordinator import SleepIQDataUpdateCoordinator
from .entity import SleepIQSensor

ICON = "mdi:bed"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed binary sensors."""
    coordinator: SleepIQDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        IsInBedBinarySensor(coordinator, bed, sleeper)
        for bed in coordinator.client.beds.values()
        for sleeper in bed.sleepers
    )


class IsInBedBinarySensor(SleepIQSensor, BinarySensorEntity):
    """Implementation of a SleepIQ presence sensor."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        bed: SleepIQBed,
        sleeper: SleepIQSleeper,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, bed, sleeper, IS_IN_BED)
        self._attr_icon = ICON

    @property
    def is_on(self) -> bool:
        """Return the status of the sensor."""
        return bool(self.sleeper.in_bed)

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend, if any."""
        return ICON_OCCUPIED if self.sleeper.in_bed else ICON_EMPTY
