"""Support for Velbus sensors."""

from __future__ import annotations

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

type VelbusSensorChannel = ButtonCounter | Temperature | LightSensor | SensorNumber


def _default_value_fn(channel) -> float | int | None:
    """Get the default state value from the channel."""
    return channel.get_state()


def _default_unit_fn(channel) -> str | None:
    """Get the default unit from the channel."""
    return channel.get_unit()


@dataclass(frozen=True, kw_only=True)
class VelbusSensorEntityDescription(SensorEntityDescription):
    """Describes Velbus sensor entity."""

    value_fn: callable = _default_value_fn
    unit_fn: callable = _default_unit_fn


SENSOR_DESCRIPTIONS: tuple[VelbusSensorEntityDescription, ...] = (
    VelbusSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    VelbusSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    VelbusSensorEntityDescription(
        key="measurement",
        state_class=SensorStateClass.MEASUREMENT,
    ),
)


def _counter_value_fn(channel) -> float | int | None:
    """Get the counter state value from the channel."""
    return channel.get_counter_state()


def _counter_unit_fn(channel) -> str | None:
    """Get the counter unit from the channel."""
    return channel.get_counter_unit()


COUNTER_DESCRIPTION = VelbusSensorEntityDescription(
    key="counter",
    device_class=SensorDeviceClass.ENERGY,
    icon="mdi:counter",
    state_class=SensorStateClass.TOTAL_INCREASING,
    value_fn=_counter_value_fn,
    unit_fn=_counter_unit_fn,
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

    _channel: VelbusSensorChannel
    entity_description: VelbusSensorEntityDescription

    def __init__(
        self,
        channel: VelbusSensorChannel,
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
