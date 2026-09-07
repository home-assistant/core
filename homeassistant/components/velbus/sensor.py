"""Support for Velbus sensors."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from velbusaio.channels import ButtonCounter, SensorNumber, Temperature
from velbusaio.properties import LightValue

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfVolume
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VelbusConfigEntry
from .entity import VelbusEntity

PARALLEL_UPDATES = 0

type VelbusSensorChannel = ButtonCounter | Temperature | LightValue | SensorNumber


@dataclass(frozen=True, kw_only=True)
class VelbusSensorEntityDescription(SensorEntityDescription):
    """Describes Velbus sensor entity."""

    value_fn: Callable[[VelbusSensorChannel], float | None] = lambda channel: float(
        channel.get_state()
    )
    unit_fn: Callable[[VelbusSensorChannel], str | None] | None = None
    unique_id_suffix: str = ""


SENSOR_DESCRIPTIONS: dict[str, VelbusSensorEntityDescription] = {
    # Instantaneous value of an electricity counter channel (power, W).
    "power": VelbusSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda channel: float(channel.get_counter_state()),
        unit_fn=lambda channel: channel.get_unit(),
    ),
    # Instantaneous value of a gas/water counter channel (flow rate, m³/h or L/h).
    "flow": VelbusSensorEntityDescription(
        key="flow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda channel: float(channel.get_state()),
        unit_fn=lambda channel: channel.get_counter_unit(),
    ),
    "temperature": VelbusSensorEntityDescription(
        key="temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        unit_fn=lambda channel: channel.get_unit(),
    ),
    "measurement": VelbusSensorEntityDescription(
        key="measurement",
        state_class=SensorStateClass.MEASUREMENT,
        unit_fn=lambda channel: channel.get_unit(),
    ),
    # Accumulating total of an electricity counter channel (energy, kWh).
    "energy": VelbusSensorEntityDescription(
        key="energy",
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda channel: (
            float(channel.energy)
            if hasattr(channel, "energy") and channel.energy is not None
            else None
        ),
        unit_fn=lambda channel: channel.get_counter_unit(),
        unique_id_suffix="-counter",
    ),
    # Accumulating total of a gas counter channel (volume, m³).
    "gas": VelbusSensorEntityDescription(
        key="gas",
        device_class=SensorDeviceClass.GAS,
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_fn=lambda channel: float(channel.get_counter_state()),
        unique_id_suffix="-counter",
    ),
    # Accumulating total of a water counter channel (volume, L).
    "water": VelbusSensorEntityDescription(
        key="water",
        device_class=SensorDeviceClass.WATER,
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value_fn=lambda channel: float(channel.get_counter_state()),
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
        if channel.is_counter_channel():
            # A counter channel exposes two entities: an instantaneous reading
            # and an accumulating total. The medium decides which pair to use.
            if channel.is_gas():
                main_key, total_key = "flow", "gas"
            elif channel.is_water():
                main_key, total_key = "flow", "water"
            else:  # electricity, or unit not yet known
                main_key, total_key = "power", "energy"
            entities.append(VelbusSensor(channel, SENSOR_DESCRIPTIONS[main_key]))
            entities.append(
                VelbusSensor(channel, SENSOR_DESCRIPTIONS[total_key], is_counter=True)
            )
        elif channel.is_temperature():
            entities.append(VelbusSensor(channel, SENSOR_DESCRIPTIONS["temperature"]))
        else:
            entities.append(VelbusSensor(channel, SENSOR_DESCRIPTIONS["measurement"]))

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
        if description.unit_fn:
            self._attr_native_unit_of_measurement = description.unit_fn(channel)
        self._attr_unique_id = f"{self._attr_unique_id}{description.unique_id_suffix}"

        # Modify name for counter entities
        if is_counter:
            self._attr_name = f"{self._attr_name}-counter"

    @property
    @override
    def native_value(self) -> float | int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._channel)
