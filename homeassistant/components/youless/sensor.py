"""The sensor entity for the Youless integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from youless_api import YoulessAPI

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_DEVICE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfVolume,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import DOMAIN
from .coordinator import YouLessCoordinator
from .entity import YouLessEntity


@dataclass(frozen=True, kw_only=True)
class YouLessSensorEntityDescription(SensorEntityDescription):
    """Describes a YouLess sensor entity."""

    device_group: str
    device_group_name: str
    value_func: Callable[[YoulessAPI], float | None]


SENSOR_TYPES: tuple[YouLessSensorEntityDescription, ...] = (
    YouLessSensorEntityDescription(
        key="water",
        device_group="water",
        device_group_name="Water meter",
        name="Water usage",
        icon="mdi:water",
        device_class=SensorDeviceClass.WATER,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_func=(
            lambda device: device.water_meter.value if device.water_meter else None
        ),
    ),
    YouLessSensorEntityDescription(
        key="gas",
        device_group="gas",
        device_group_name="Gas meter",
        name="Gas usage",
        icon="mdi:fire",
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_func=lambda device: device.gas_meter.value if device.gas_meter else None,
    ),
    YouLessSensorEntityDescription(
        key="usage",
        device_group="power",
        device_group_name="Power usage",
        name="Power Usage",
        icon="mdi:meter-electric",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_func=(
            lambda device: device.current_power_usage.value
            if device.current_power_usage
            else None
        ),
    ),
    YouLessSensorEntityDescription(
        key="power_low",
        device_group="power",
        device_group_name="Power usage",
        name="Energy low",
        icon="mdi:transmission-tower-export",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_func=(
            lambda device: device.power_meter.low.value if device.power_meter else None
        ),
    ),
    YouLessSensorEntityDescription(
        key="power_high",
        device_group="power",
        device_group_name="Power usage",
        name="Energy high",
        icon="mdi:transmission-tower-export",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_func=(
            lambda device: device.power_meter.high.value if device.power_meter else None
        ),
    ),
    YouLessSensorEntityDescription(
        key="power_total",
        device_group="power",
        device_group_name="Power usage",
        name="Energy total",
        icon="mdi:transmission-tower-export",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_func=(
            lambda device: device.power_meter.total.value
            if device.power_meter
            else None
        ),
    ),
    YouLessSensorEntityDescription(
        key="phase_1_power",
        device_group="power",
        device_group_name="Power usage",
        name="Phase 1 power",
        icon=None,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_func=lambda device: device.phase1.power.value if device.phase1 else None,
    ),
    YouLessSensorEntityDescription(
        key="phase_1_voltage",
        device_group="power",
        device_group_name="Power usage",
        name="Phase 1 voltage",
        icon=None,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_func=(
            lambda device: device.phase1.voltage.value if device.phase1 else None
        ),
    ),
    YouLessSensorEntityDescription(
        key="phase_1_current",
        device_group="power",
        device_group_name="Power usage",
        name="Phase 1 current",
        icon=None,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_func=(
            lambda device: device.phase1.current.value if device.phase1 else None
        ),
    ),
    YouLessSensorEntityDescription(
        key="phase_2_power",
        device_group="power",
        device_group_name="Power usage",
        name="Phase 2 power",
        icon=None,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_func=lambda device: device.phase2.power.value if device.phase2 else None,
    ),
    YouLessSensorEntityDescription(
        key="phase_2_voltage",
        device_group="power",
        device_group_name="Power usage",
        name="Phase 2 voltage",
        icon=None,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_func=(
            lambda device: device.phase2.voltage.value if device.phase2 else None
        ),
    ),
    YouLessSensorEntityDescription(
        key="phase_2_current",
        device_group="power",
        device_group_name="Power usage",
        name="Phase 2 current",
        icon=None,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_func=(
            lambda device: device.phase2.current.value if device.phase1 else None
        ),
    ),
    YouLessSensorEntityDescription(
        key="phase_3_power",
        device_group="power",
        device_group_name="Power usage",
        name="Phase 3 power",
        icon=None,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_func=lambda device: device.phase3.power.value if device.phase3 else None,
    ),
    YouLessSensorEntityDescription(
        key="phase_3_voltage",
        device_group="power",
        device_group_name="Power usage",
        name="Phase 3 voltage",
        icon=None,
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        value_func=(
            lambda device: device.phase3.voltage.value if device.phase3 else None
        ),
    ),
    YouLessSensorEntityDescription(
        key="phase_3_current",
        device_group="power",
        device_group_name="Power usage",
        name="Phase 3 current",
        icon=None,
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_func=(
            lambda device: device.phase3.current.value if device.phase1 else None
        ),
    ),
    YouLessSensorEntityDescription(
        key="delivery_low",
        device_group="delivery",
        device_group_name="Energy delivery",
        name="Energy delivery low",
        icon="mdi:transmission-tower-import",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_func=(
            lambda device: device.delivery_meter.low.value
            if device.delivery_meter
            else None
        ),
    ),
    YouLessSensorEntityDescription(
        key="delivery_high",
        device_group="delivery",
        device_group_name="Energy delivery",
        name="Energy delivery high",
        icon="mdi:transmission-tower-import",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_func=(
            lambda device: device.delivery_meter.high.value
            if device.delivery_meter
            else None
        ),
    ),
    YouLessSensorEntityDescription(
        key="extra_total",
        device_group="extra",
        device_group_name="Extra meter",
        name="Extra total",
        icon="mdi:meter-electric",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        value_func=(
            lambda device: device.extra_meter.total.value
            if device.extra_meter
            else None
        ),
    ),
    YouLessSensorEntityDescription(
        key="extra_usage",
        device_group="extra",
        device_group_name="Extra meter",
        name="Extra usage",
        icon="mdi:lightning-bolt",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_func=(
            lambda device: device.extra_meter.usage.value
            if device.extra_meter
            else None
        ),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Initialize the integration."""
    coordinator: YouLessCoordinator = hass.data[DOMAIN][entry.entry_id]
    device = entry.data[CONF_DEVICE]
    if (device := entry.data[CONF_DEVICE]) is None:
        device = entry.entry_id

    async_add_entities(
        [
            YouLessSensor(coordinator, description, device)
            for description in SENSOR_TYPES
        ]
    )


class YouLessSensor(YouLessEntity, SensorEntity):
    """Representation of a Sensor."""

    entity_description: YouLessSensorEntityDescription

    def __init__(
        self,
        coordinator: YouLessCoordinator,
        description: YouLessSensorEntityDescription,
        device: str,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(
            coordinator,
            f"{device}_{description.device_group}",
            description.device_group_name,
        )
        self._attr_unique_id = f"{DOMAIN}_{device}_{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_func(self.device)
