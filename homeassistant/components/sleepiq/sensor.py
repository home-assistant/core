"""Support for SleepIQ sensors."""
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BED, DOMAIN, SIDES, SLEEP_NUMBER
from .coordinator import SleepIQDataUpdateCoordinator
from .entity import SleepIQSensor


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed sensors."""
    coordinator: SleepIQDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]
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
        self._attr_native_value = self.side_data.sleep_number
