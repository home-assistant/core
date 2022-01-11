"""Support for SleepIQ sensors."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DATA_SLEEPIQ, SleepIQDataUpdateCoordinator, SleepIQSensor
from .const import BED, SIDES, SLEEP_NUMBER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed sensors."""
    coordinator = hass.data[DATA_SLEEPIQ].coordinators[config_entry.data[CONF_USERNAME]]
    entities = []

    for bed_id in coordinator.data:
        for side in SIDES:
            if getattr(coordinator.data[bed_id][BED], side) is not None:
                entities.append(SleepNumberSensor(coordinator, bed_id, side))

    async_add_entities(entities, True)


class SleepNumberSensor(SleepIQSensor, SensorEntity):
    """Implementation of a SleepIQ sensor."""

    def __init__(
        self,
        coordinator: SleepIQDataUpdateCoordinator,
        bed_id: str,
        side: str,
    ) -> None:
        """Initialize the SleepIQ sleep number sensor."""
        super().__init__(coordinator, bed_id, side)
        self._name = SLEEP_NUMBER

    @property
    def native_value(self) -> int:
        """Return the state of the sensor."""
        return self._side.sleep_number
