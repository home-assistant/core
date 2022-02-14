"""Support for SleepIQ sensors."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DATA_SLEEPIQ, SleepIQDataUpdateCoordinator, SleepIQSensor
from .const import BED, SIDES, SLEEP_NUMBER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed sensors."""
    coordinator: SleepIQDataUpdateCoordinator = hass.data[DATA_SLEEPIQ].coordinators[
        config_entry.data[CONF_USERNAME]
    ]
    async_add_entities(
        SleepNumberSensor(coordinator, bed_id, side)
        for side in SIDES
        for bed_id in coordinator.data
        if getattr(coordinator.data[bed_id][BED], side) is not None
    )


class SleepNumberSensor(SleepIQSensor, SensorEntity):
    """Implementation of a SleepIQ sensor."""

    def __init__(
        self,
        coordinator: SleepIQDataUpdateCoordinator,
        bed_id: str,
        side: str,
    ) -> None:
        """Initialize the SleepIQ sleep number sensor."""
        super().__init__(coordinator, bed_id, side, SLEEP_NUMBER)

    @callback
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
        super()._async_update_attrs()
        self._attr_native_value = self._side.sleep_number
