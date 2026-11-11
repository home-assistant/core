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
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VelbusConfigEntry
from .entity import VelbusEntity

PARALLEL_UPDATES = 0

COUNTER_SENSOR_KEYS = frozenset({"energy", "gas", "water"})

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
    "power": VelbusSensorEntityDescription(
        key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_fn=lambda channel: float(
            channel.get_counter_state()
            if isinstance(channel, ButtonCounter)
            else channel.get_state()
        ),
    ),
    "voltage": VelbusSensorEntityDescription(
        key="voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
    ),
    "current": VelbusSensorEntityDescription(
        key="current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
    ),
    "load": VelbusSensorEntityDescription(
        key="load",
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
    ),
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
    "energy": VelbusSensorEntityDescription(
        key="energy",
        device_class=SensorDeviceClass.ENERGY,
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_fn=lambda channel: (
            float(channel.energy)
            if hasattr(channel, "energy") and channel.energy is not None
            else None
        ),
        unique_id_suffix="-counter",
    ),
    "gas": VelbusSensorEntityDescription(
        key="gas",
        device_class=SensorDeviceClass.GAS,
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_fn=lambda channel: (
            float(total)
            if isinstance(channel, ButtonCounter)
            and (total := channel.get_counter_total()) is not None
            else None
        ),
        unique_id_suffix="-counter",
    ),
    "water": VelbusSensorEntityDescription(
        key="water",
        device_class=SensorDeviceClass.WATER,
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.LITERS,
        value_fn=lambda channel: (
            float(total)
            if isinstance(channel, ButtonCounter)
            and (total := channel.get_counter_total()) is not None
            else None
        ),
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
        entities.extend(
            VelbusSensor(
                channel,
                SENSOR_DESCRIPTIONS[sensor_type],
                is_counter=sensor_type in COUNTER_SENSOR_KEYS,
            )
            for sensor_type in channel.get_sensor_types()
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
        if description.unit_fn:
            self._attr_native_unit_of_measurement = description.unit_fn(channel)
        self._attr_unique_id = f"{self._attr_unique_id}{description.unique_id_suffix}"

        if is_counter:
            self._attr_translation_key = "counter"
            self._attr_translation_placeholders = {"channel_name": channel.get_name()}
            del self._attr_name

    @override
    def _default_to_device_class_name(self) -> bool:
        """Use entity translations instead of device class for counter totals."""
        if self._is_counter:
            return False
        return super()._default_to_device_class_name()

    @property
    @override
    def native_value(self) -> float | int | None:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self._channel)
