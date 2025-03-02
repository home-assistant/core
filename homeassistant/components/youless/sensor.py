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
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import DOMAIN
from .coordinator import YouLessCoordinator
from .entity import YouLessEntity


@dataclass(frozen=True, kw_only=True)
class YouLessSensorEntityDescription(SensorEntityDescription):
    """Describes a YouLess sensor entity."""

    device_group: str
    value_func: Callable[[YoulessAPI], float | None | str]


SENSOR_TYPES: tuple[YouLessSensorEntityDescription, ...] = (
    YouLessSensorEntityDescription(
        key="water",
        device_group="water",
        translation_key="total_water",
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
        translation_key="total_gas_m3",
        device_class=SensorDeviceClass.GAS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        value_func=lambda device: device.gas_meter.value if device.gas_meter else None,
    ),
    YouLessSensorEntityDescription(
        key="usage",
        device_group="power",
        translation_key="active_power_w",
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
        translation_key="total_energy_import_tariff_kwh",
        translation_placeholders={"tariff": "1"},
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
        translation_key="total_energy_import_tariff_kwh",
        translation_placeholders={"tariff": "2"},
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
        translation_key="total_energy_import_kwh",
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
        translation_key="active_power_phase_w",
        translation_placeholders={"phase": "1"},
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_func=lambda device: device.phase1.power.value if device.phase1 else None,
    ),
    YouLessSensorEntityDescription(
        key="phase_1_voltage",
        device_group="power",
        translation_key="active_voltage_phase_v",
        translation_placeholders={"phase": "1"},
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
        translation_key="active_current_phase_a",
        translation_placeholders={"phase": "1"},
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
        translation_key="active_power_phase_w",
        translation_placeholders={"phase": "2"},
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_func=lambda device: device.phase2.power.value if device.phase2 else None,
    ),
    YouLessSensorEntityDescription(
        key="phase_2_voltage",
        device_group="power",
        translation_key="active_voltage_phase_v",
        translation_placeholders={"phase": "2"},
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
        translation_key="active_current_phase_a",
        translation_placeholders={"phase": "2"},
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
        translation_key="active_power_phase_w",
        translation_placeholders={"phase": "3"},
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_func=lambda device: device.phase3.power.value if device.phase3 else None,
    ),
    YouLessSensorEntityDescription(
        key="phase_3_voltage",
        device_group="power",
        translation_key="active_voltage_phase_v",
        translation_placeholders={"phase": "3"},
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
        translation_key="active_current_phase_a",
        translation_placeholders={"phase": "3"},
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        value_func=(
            lambda device: device.phase3.current.value if device.phase1 else None
        ),
    ),
    YouLessSensorEntityDescription(
        key="tariff",
        device_group="power",
        translation_key="active_tariff",
        device_class=SensorDeviceClass.ENUM,
        options=["1", "2"],
        value_func=(
            lambda device: str(device.current_tariff) if device.current_tariff else None
        ),
    ),
    YouLessSensorEntityDescription(
        key="average_peak",
        device_group="power",
        translation_key="average_peak",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_func=(
            lambda device: device.average_power.value if device.average_power else None
        ),
    ),
    YouLessSensorEntityDescription(
        key="month_peak",
        device_group="power",
        translation_key="month_peak",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.WATT,
        value_func=(
            lambda device: device.peak_power.value if device.peak_power else None
        ),
    ),
    YouLessSensorEntityDescription(
        key="delivery_low",
        device_group="delivery",
        translation_key="total_energy_export_tariff_kwh",
        translation_placeholders={"tariff": "1"},
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
        translation_key="total_energy_export_tariff_kwh",
        translation_placeholders={"tariff": "2"},
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
        translation_key="total_s0_kwh",
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
        translation_key="active_s0_w",
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
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
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
    _attr_has_entity_name = True

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
            description.device_group,
        )
        self._attr_unique_id = f"{DOMAIN}_{device}_{description.key}"
        self.entity_description = description

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_func(self.device)
