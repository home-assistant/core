"""Support for SleepIQ sensors."""
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SLEEPIQ_DATA, SLEEPIQ_STATUS_COORDINATOR, ICON_EMPTY, ICON_OCCUPIED
from .coordinator import SleepIQDataUpdateCoordinator

ICON = "mdi:bed"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed binary sensors."""
    coordinator: SleepIQDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id][SLEEPIQ_STATUS_COORDINATOR]
    data = hass.data[DOMAIN][entry.entry_id][SLEEPIQ_DATA]
    entities: list[IsInBedBinarySensor] = []
    for bed in data.beds.values():
        for sleeper in bed.sleepers:
            entities.append(IsInBedBinarySensor(coordinator, bed, sleeper))

    async_add_entities(entities)


class IsInBedBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Implementation of a SleepIQ presence sensor."""

    self._attr_device_class = BinarySensorDeviceClass.OCCUPANCY
    def __init__(self,
        coordinator: SleepIQDataUpdateCoordinator,
         bed,sleeper):
        """Initialize the sensor."""
        super().__init__(status_coordinator)
        super().__init__(coordinator, bed_id, side, IS_IN_BED)
        self._bed = bed
        self._sleeper = sleeper
        self._attr_name = f"SleepNumber {bed.name} {sleeper.name} Is In Bed"
        self._attr_unique_id = f"{bed.id}-{sleeper.side}-InBed"
        self._attr_icon = ICON

    @property
    def is_on(self):
        """Return the status of the sensor."""
        return self._sleeper.in_bed

    @callback
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
        super()._async_update_attrs()
        self._attr_is_on = getattr(self.side_data, IS_IN_BED)
        self._attr_icon = ICON_OCCUPIED if self.is_on else ICON_EMPTY