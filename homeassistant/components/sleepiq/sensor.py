"""Support for SleepIQ sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from asyncsleepiq import SleepIQBed, SleepIQSleeper

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN, PRESSURE, SLEEP_NUMBER
from .coordinator import SleepIQData, SleepIQDataUpdateCoordinator
from .entity import SleepIQSleeperEntity


@dataclass(frozen=True, kw_only=True)
class SleepIQSensorEntityDescription(SensorEntityDescription):
    """Describes SleepIQ sensor entity."""

    value_fn: Callable[[SleepIQSleeper], float | int | None]


SENSORS: tuple[SleepIQSensorEntityDescription, ...] = (
    SleepIQSensorEntityDescription(
        key=PRESSURE,
        translation_key="pressure",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sleeper: sleeper.pressure,
    ),
    SleepIQSensorEntityDescription(
        key=SLEEP_NUMBER,
        translation_key="sleep_number",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda sleeper: sleeper.sleep_number,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the SleepIQ bed sensors."""
    data: SleepIQData = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        SleepIQSensorEntity(data.data_coordinator, bed, sleeper, description)
        for bed in data.client.beds.values()
        for sleeper in bed.sleepers
        for description in SENSORS
    )


class SleepIQSensorEntity(
    SleepIQSleeperEntity[SleepIQDataUpdateCoordinator], SensorEntity
):
    """Representation of a SleepIQ sensor."""

    entity_description: SleepIQSensorEntityDescription

    def __init__(
        self,
        coordinator: SleepIQDataUpdateCoordinator,
        bed: SleepIQBed,
        sleeper: SleepIQSleeper,
        description: SleepIQSensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        super().__init__(coordinator, bed, sleeper, description.key)

    @callback
    def _async_update_attrs(self) -> None:
        """Update sensor attributes."""
        self._attr_native_value = self.entity_description.value_fn(self.sleeper)
