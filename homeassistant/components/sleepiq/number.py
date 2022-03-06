"""Support for SleepIQ SleepNumber firmness number entities."""
from asyncsleepiq import SleepIQActuator, SleepIQBed, SleepIQSleeper

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import ACTUATOR, DOMAIN, FIRMNESS, SENSOR_TYPES
from .coordinator import SleepIQData
from .entity import SleepIQBedEntity, SleepIQSleeperEntity


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
    async_add_entities(
        SleepNumberActuatorEntity(data.data_coordinator, bed, actuator)
        for bed in data.client.beds.values()
        for actuator in bed.foundation.actuators
    )


class SleepNumberFirmnessEntity(SleepIQSleeperEntity, NumberEntity):
    """Representation of a SleepIQ entity with CoordinatorEntity."""

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
        """Initialize the number."""
        super().__init__(coordinator, bed, sleeper, FIRMNESS)

    @callback
    def _async_update_attrs(self) -> None:
        """Update number attributes."""
        self._attr_value = float(self.sleeper.sleep_number)

    async def async_set_value(self, value: float) -> None:
        """Set the firmness value."""
        await self.sleeper.set_sleepnumber(int(value))
        self._attr_value = value
        self.async_write_ha_state()


class SleepNumberActuatorEntity(SleepIQBedEntity, NumberEntity):
    """Representation of a SleepIQ entity with CoordinatorEntity."""

    _attr_icon = "mdi:bed"
    _attr_max_value: float = 100
    _attr_min_value: float = 0
    _attr_step: float = 1

    def __init__(
        self,
        coordinator: DataUpdateCoordinator,
        bed: SleepIQBed,
        actuator: SleepIQActuator,
    ) -> None:
        """Initialize the number."""
        self.actuator = actuator
        super().__init__(coordinator, bed)

        self._attr_name = (
            f"SleepNumber {bed.name} {actuator.side_full} {actuator.actuator_full} {SENSOR_TYPES[ACTUATOR]}"
            if actuator.side
            else f"SleepNumber {bed.name} {actuator.actuator_full} {SENSOR_TYPES[ACTUATOR]}"
        )
        self._attr_unique_id = (
            f"{bed.id}_{actuator.side}_{actuator.actuator}"
            if actuator.side
            else f"{bed.id}_{actuator.actuator}"
        )

    @callback
    def _async_update_attrs(self) -> None:
        """Update number attributes."""
        self._attr_value = self.actuator.position

    async def async_set_value(self, value: float) -> None:
        """Set the actuator position."""
        await self.actuator.set_position(int(value))
        self._attr_value = value
        self.async_write_ha_state()
