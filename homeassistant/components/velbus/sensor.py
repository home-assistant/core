"""Support for Velbus sensors."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from velbusaio.channels import ButtonCounter, LightSensor, SensorNumber, Temperature

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VelbusConfigEntry
from .entity import VelbusEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class VelbusSensorEntityDescription(SensorEntityDescription):
    """Describes Velbus sensor entity."""

    value_fn: Callable[
        [ButtonCounter | Temperature | LightSensor | SensorNumber], float | int | None
    ]
    unit_fn: Callable[
        [ButtonCounter | Temperature | LightSensor | SensorNumber], str | None
    ]


SENSOR_DESCRIPTIONS: tuple[VelbusSensorEntityDescription, ...] = (
    VelbusSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda channel: float(channel.get_state()),
        unit_fn=lambda channel: channel.get_unit(),
    ),
    VelbusSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda channel: float(channel.get_state()),
        unit_fn=lambda channel: channel.get_unit(),
    ),
    VelbusSensorEntityDescription(
        key="measurement",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda channel: float(channel.get_state()),
        unit_fn=lambda channel: channel.get_unit(),
    ),
)

COUNTER_DESCRIPTION = VelbusSensorEntityDescription(
    key="counter",
    device_class=SensorDeviceClass.ENERGY,
    icon="mdi:counter",
    state_class=SensorStateClass.TOTAL_INCREASING,
    value_fn=lambda channel: float(channel.get_counter_state()),
    unit_fn=lambda channel: channel.get_counter_unit(),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Velbus switch based on config_entry."""
    await entry.runtime_data.scan_task
    entities: list[VelbusSensor] = []
    for channel in entry.runtime_data.controller.get_all_sensor():
        # Determine which description to use for the main sensor
        if channel.is_counter_channel():
            description = SENSOR_DESCRIPTIONS[0]  # power
        elif channel.is_temperature():
            description = SENSOR_DESCRIPTIONS[1]  # temperature
        else:
            description = SENSOR_DESCRIPTIONS[2]  # measurement

        entities.append(VelbusSensor(channel, description))

        # Add counter entity if applicable
        if channel.is_counter_channel():
            entities.append(VelbusSensor(channel, COUNTER_DESCRIPTION, is_counter=True))

    async_add_entities(entities)


class VelbusSensor(VelbusEntity, SensorEntity):
    """Representation of a sensor."""

    _channel: ButtonCounter | Temperature | LightSensor | SensorNumber
    entity_description: VelbusSensorEntityDescription

    def __init__(
        self,
        channel: ButtonCounter | Temperature | LightSensor | SensorNumber,
        description: VelbusSensorEntityDescription,
        is_counter: bool = False,
    ) -> None:
        """Initialize a sensor Velbus entity."""
        super().__init__(channel)
        self.entity_description = description
        self._is_counter = is_counter

        # Set unit of measurement
        self._attr_native_unit_of_measurement = description.unit_fn(channel)

        # Modify unique_id and name for counter entities
        if is_counter:
            self._attr_unique_id = f"{self._attr_unique_id}-counter"
            self._attr_name = f"{self._attr_name}-counter"

    @property
    def native_value(self) -> float | int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._channel)
