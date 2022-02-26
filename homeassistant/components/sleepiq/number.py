"""Support for SleepIQ SleepNumber firmness number entities."""
from asyncsleepiq import SleepIQBed, SleepIQSleeper

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import DOMAIN, FIRMNESS
from .coordinator import SleepIQData
from .entity import SleepIQSensor


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed sensors."""
    data: SleepIQData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SleepNumberFirmnessEntity(data.data_coordinator, bed, sleeper)
        for bed in data.client.beds.values()
        for sleeper in bed.sleepers
    )


class SleepNumberFirmnessEntity(SleepIQSensor, NumberEntity):
    """Representation of an SleepIQ Entity with CoordinatorEntity."""

    _attr_icon = "mdi:bed"
    _attr_max_value: float = 100
    _attr_min_value: float = 5
    _attr_step: float = 5

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        bed: SleepIQBed,
        sleeper: SleepIQSleeper,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator, bed, sleeper, FIRMNESS)

    @callback
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
        self._attr_value = float(self.sleeper.sleep_number)

    async def async_set_value(self, value: float) -> None:
        """Set the firmness value."""
        await self.sleeper.set_sleepnumber(value)
