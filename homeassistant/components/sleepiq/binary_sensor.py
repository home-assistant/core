"""Support for SleepIQ sensors."""
from asyncsleepiq import (
    SleepIQBed,
    SleepIQSleeper,
)
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.core import HomeAssistant, callback

from .const import (
    DOMAIN,
    SLEEPIQ_DATA,
    SLEEPIQ_STATUS_COORDINATOR,
    ICON_EMPTY,
    ICON_OCCUPIED,
    IS_IN_BED,
)
from .entity import SleepIQSensor

ICON = "mdi:bed"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed binary sensors."""
    coordinator: DataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][
        SLEEPIQ_STATUS_COORDINATOR
    ]
    data = hass.data[DOMAIN][entry.entry_id][SLEEPIQ_DATA]
    entities: list[IsInBedBinarySensor] = []
    for bed in data.beds.values():
        for sleeper in bed.sleepers:
            entities.append(IsInBedBinarySensor(coordinator, bed, sleeper))

    async_add_entities(entities)


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
    def is_on(self):
        """Return the status of the sensor."""
        return self.sleeper.in_bed

    @callback
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
        super()._async_update_attrs()
        self._attr_is_on = getattr(self.side_data, IS_IN_BED)
        self._attr_icon = ICON_OCCUPIED if self.is_on else ICON_EMPTY
