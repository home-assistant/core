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

type VelbusSensorChannel = ButtonCounter | Temperature | LightSensor | SensorNumber


@dataclass(frozen=True, kw_only=True)
class VelbusSensorEntityDescription(SensorEntityDescription):
    """Describes Velbus sensor entity."""

    value_fn: Callable[[VelbusSensorChannel], float | None] = lambda channel: float(
        channel.get_state()
    )
    unit_fn: Callable[[VelbusSensorChannel], str | None] = (
        lambda channel: channel.get_unit()
    )
    unique_id_suffix: str = ""


SENSOR_DESCRIPTIONS: dict[str, VelbusSensorEntityDescription] = {
    "power": VelbusSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "temperature": VelbusSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "measurement": VelbusSensorEntityDescription(
        key="measurement",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    "counter": VelbusSensorEntityDescription(
        key="counter",
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda channel: float(channel.get_counter_state()),
        unit_fn=lambda channel: channel.get_counter_unit(),
        unique_id_suffix="-counter",
    ),
}


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
            description = SENSOR_DESCRIPTIONS["power"]
        elif channel.is_temperature():
            description = SENSOR_DESCRIPTIONS["temperature"]
        else:
            description = SENSOR_DESCRIPTIONS["measurement"]

        entities.append(VelbusSensor(channel, description))

        # Add counter entity if applicable
        if channel.is_counter_channel():
            entities.append(
                VelbusSensor(channel, SENSOR_DESCRIPTIONS["counter"], is_counter=True)
            )

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
        self._attr_native_unit_of_measurement = description.unit_fn(channel)
        self._attr_unique_id = f"{self._attr_unique_id}{description.unique_id_suffix}"

        # Modify name for counter entities
        if is_counter:
            self._attr_name = f"{self._attr_name}-counter"

    @property
    def native_value(self) -> float | int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._channel)
