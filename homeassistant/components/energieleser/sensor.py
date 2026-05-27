"""Sensor platform for the energieleser integration."""

from collections.abc import Callable
from dataclasses import dataclass

from energieleser import (
    GasleserDevice,
    StromleserOneDevice,
    WaermeleserDevice,
    WasserleserDevice,
)

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_HOST,
    SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, device_model_name
from .coordinator import EnergieleserConfigEntry, EnergieleserCoordinator

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class StromleserSensorEntityDescription(SensorEntityDescription):
    """Describes a stromleser sensor."""

    value_fn: Callable[[StromleserOneDevice], StateType]
    unit_fn: Callable[[StromleserOneDevice], str | None] | None = None
    available_fn: Callable[[StromleserOneDevice], bool] = lambda _: True


@dataclass(frozen=True, kw_only=True)
class GasleserSensorEntityDescription(SensorEntityDescription):
    """Describes a gasleser sensor."""

    value_fn: Callable[[GasleserDevice], StateType]
    available_fn: Callable[[GasleserDevice], bool] = lambda _: True


@dataclass(frozen=True, kw_only=True)
class WasserleserSensorEntityDescription(SensorEntityDescription):
    """Describes a wasserleser sensor."""

    value_fn: Callable[[WasserleserDevice], StateType]
    available_fn: Callable[[WasserleserDevice], bool] = lambda _: True


@dataclass(frozen=True, kw_only=True)
class WaermeleserSensorEntityDescription(SensorEntityDescription):
    """Describes a wärmeleser sensor."""

    value_fn: Callable[[WaermeleserDevice], StateType]
    available_fn: Callable[[WaermeleserDevice], bool] = lambda _: True


STROMLESER_SENSORS: tuple[StromleserSensorEntityDescription, ...] = (
    StromleserSensorEntityDescription(
        key="energy_import",
        translation_key="energy_import",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.energy_import.value if d.energy_import else None,
        unit_fn=lambda d: d.energy_import.unit if d.energy_import else None,
        available_fn=lambda d: d.energy_import is not None,
    ),
    StromleserSensorEntityDescription(
        key="energy_export",
        translation_key="energy_export",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.energy_export.value if d.energy_export else None,
        unit_fn=lambda d: d.energy_export.unit if d.energy_export else None,
        available_fn=lambda d: d.energy_export is not None,
    ),
    StromleserSensorEntityDescription(
        key="power_active",
        translation_key="power_total",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.power_active.value if d.power_active else None,
        unit_fn=lambda d: d.power_active.unit if d.power_active else None,
        available_fn=lambda d: d.power_active is not None,
    ),
    StromleserSensorEntityDescription(
        key="power_l1",
        translation_key="power_l1",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.power_l1.value if d.power_l1 else None,
        unit_fn=lambda d: d.power_l1.unit if d.power_l1 else None,
        available_fn=lambda d: d.power_l1 is not None,
    ),
    StromleserSensorEntityDescription(
        key="power_l2",
        translation_key="power_l2",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.power_l2.value if d.power_l2 else None,
        unit_fn=lambda d: d.power_l2.unit if d.power_l2 else None,
        available_fn=lambda d: d.power_l2 is not None,
    ),
    StromleserSensorEntityDescription(
        key="power_l3",
        translation_key="power_l3",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.power_l3.value if d.power_l3 else None,
        unit_fn=lambda d: d.power_l3.unit if d.power_l3 else None,
        available_fn=lambda d: d.power_l3 is not None,
    ),
    StromleserSensorEntityDescription(
        key="signal_strength_dbm",
        translation_key="signal_strength_dbm",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.signal_strength_dbm,
        available_fn=lambda d: d.signal_strength_dbm is not None,
    ),
)

GASLESER_SENSORS: tuple[GasleserSensorEntityDescription, ...] = (
    GasleserSensorEntityDescription(
        key="total_consumption",
        translation_key="gas_consumption",
        device_class=SensorDeviceClass.GAS,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.total_consumption,
        available_fn=lambda d: d.total_consumption is not None,
    ),
    GasleserSensorEntityDescription(
        key="current_flow_rate",
        translation_key="flow_rate",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.current_flow_rate,
        available_fn=lambda d: d.current_flow_rate is not None,
    ),
    GasleserSensorEntityDescription(
        key="count",
        translation_key="pulse_count",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.count,
        available_fn=lambda d: d.count is not None,
    ),
    GasleserSensorEntityDescription(
        key="signal_strength_dbm",
        translation_key="signal_strength_dbm",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.signal_strength_dbm,
        available_fn=lambda d: d.signal_strength_dbm is not None,
    ),
)

WASSERLESER_SENSORS: tuple[WasserleserSensorEntityDescription, ...] = (
    WasserleserSensorEntityDescription(
        key="total_consumption",
        translation_key="water_consumption",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.total_consumption.value if d.total_consumption else None,
        available_fn=lambda d: d.total_consumption is not None,
    ),
    WasserleserSensorEntityDescription(
        key="today_consumption",
        translation_key="water_today_consumption",
        device_class=SensorDeviceClass.WATER,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.today_consumption.value if d.today_consumption else None,
        available_fn=lambda d: d.today_consumption is not None,
    ),
    WasserleserSensorEntityDescription(
        key="current_flow_rate",
        translation_key="water_flow_rate",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.current_flow_rate.value if d.current_flow_rate else None,
        available_fn=lambda d: d.current_flow_rate is not None,
    ),
    WasserleserSensorEntityDescription(
        key="current_flow_rate_m3",
        translation_key="water_flow_rate_m3",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=(
            lambda d: d.current_flow_rate_m3.value if d.current_flow_rate_m3 else None
        ),
        available_fn=lambda d: d.current_flow_rate_m3 is not None,
    ),
    WasserleserSensorEntityDescription(
        key="signal_strength_dbm",
        translation_key="signal_strength_dbm",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.signal_strength_dbm,
        available_fn=lambda d: d.signal_strength_dbm is not None,
    ),
)

WAERMELESER_SENSORS: tuple[WaermeleserSensorEntityDescription, ...] = (
    WaermeleserSensorEntityDescription(
        key="total_energy_t1",
        translation_key="heat_energy_tariff_1",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.total_energy_t1.value if d.total_energy_t1 else None,
        available_fn=lambda d: d.total_energy_t1 is not None,
    ),
    WaermeleserSensorEntityDescription(
        key="total_energy_t2",
        translation_key="heat_energy_tariff_2",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.total_energy_t2.value if d.total_energy_t2 else None,
        available_fn=lambda d: d.total_energy_t2 is not None,
    ),
    WaermeleserSensorEntityDescription(
        key="total_energy_t3",
        translation_key="heat_energy_tariff_3",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.total_energy_t3.value if d.total_energy_t3 else None,
        available_fn=lambda d: d.total_energy_t3 is not None,
    ),
    WaermeleserSensorEntityDescription(
        key="power",
        translation_key="heat_power",
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.power.value if d.power else None,
        available_fn=lambda d: d.power is not None,
    ),
    WaermeleserSensorEntityDescription(
        key="total_volume",
        translation_key="heat_total_volume",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.total_volume.value if d.total_volume else None,
        available_fn=lambda d: d.total_volume is not None,
    ),
    WaermeleserSensorEntityDescription(
        key="volume_flow",
        translation_key="heat_volume_flow",
        device_class=SensorDeviceClass.VOLUME_FLOW_RATE,
        native_unit_of_measurement=UnitOfVolumeFlowRate.LITERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.volume_flow.value if d.volume_flow else None,
        available_fn=lambda d: d.volume_flow is not None,
    ),
    WaermeleserSensorEntityDescription(
        key="flow_temperature",
        translation_key="heat_flow_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.flow_temperature.value if d.flow_temperature else None,
        available_fn=lambda d: d.flow_temperature is not None,
    ),
    WaermeleserSensorEntityDescription(
        key="return_temperature",
        translation_key="heat_return_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.return_temperature.value if d.return_temperature else None,
        available_fn=lambda d: d.return_temperature is not None,
    ),
    WaermeleserSensorEntityDescription(
        key="temperature_difference",
        translation_key="heat_temperature_difference",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.KELVIN,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=(
            lambda d: (
                d.temperature_difference.value if d.temperature_difference else None
            )
        ),
        available_fn=lambda d: d.temperature_difference is not None,
    ),
    WaermeleserSensorEntityDescription(
        key="signal_strength_dbm",
        translation_key="signal_strength_dbm",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda d: d.signal_strength_dbm,
        available_fn=lambda d: d.signal_strength_dbm is not None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: EnergieleserConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up energieleser sensors from a config entry."""
    coordinator = entry.runtime_data
    device = coordinator.data

    if isinstance(device, StromleserOneDevice):
        async_add_entities(
            StromleserSensor(coordinator=coordinator, description=description)
            for description in STROMLESER_SENSORS
            if description.available_fn(device)
        )
    elif isinstance(device, GasleserDevice):
        async_add_entities(
            GasleserSensor(coordinator=coordinator, description=description)
            for description in GASLESER_SENSORS
            if description.available_fn(device)
        )
    elif isinstance(device, WasserleserDevice):
        async_add_entities(
            WasserleserSensor(coordinator=coordinator, description=description)
            for description in WASSERLESER_SENSORS
            if description.available_fn(device)
        )
    elif isinstance(device, WaermeleserDevice):
        async_add_entities(
            WaermeleserSensor(coordinator=coordinator, description=description)
            for description in WAERMELESER_SENSORS
            if description.available_fn(device)
        )


class _EnergieleserSensorBase(CoordinatorEntity[EnergieleserCoordinator], SensorEntity):
    """Common base for energieleser sensors."""

    _attr_has_entity_name = True

    def __init__(
        self,
        *,
        coordinator: EnergieleserCoordinator,
        description: SensorEntityDescription,
    ) -> None:
        """Initialise the sensor."""
        super().__init__(coordinator=coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_id}_{description.key}"
        host = coordinator.config_entry.data[CONF_HOST]
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.device_id)},
            name=coordinator.device_id,
            manufacturer="nineti GmbH",
            model=device_model_name(coordinator.device_type),
            # Only wärmeleser devices report a fabrication number; others omit it.
            serial_number=getattr(coordinator.data, "fabrication_number", None),
            configuration_url=f"http://{host}/",
        )


class StromleserSensor(_EnergieleserSensorBase):
    """Sensor entity for a stromleser device."""

    entity_description: StromleserSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        device = self.coordinator.data
        assert isinstance(device, StromleserOneDevice)
        return self.entity_description.value_fn(device)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit, preferring the device-reported one when available."""
        if self.entity_description.unit_fn is not None:
            device = self.coordinator.data
            assert isinstance(device, StromleserOneDevice)
            unit = self.entity_description.unit_fn(device)
            if unit:
                return unit
        return self.entity_description.native_unit_of_measurement


class GasleserSensor(_EnergieleserSensorBase):
    """Sensor entity for a gasleser device."""

    entity_description: GasleserSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        device = self.coordinator.data
        assert isinstance(device, GasleserDevice)
        return self.entity_description.value_fn(device)


class WasserleserSensor(_EnergieleserSensorBase):
    """Sensor entity for a wasserleser device."""

    entity_description: WasserleserSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        device = self.coordinator.data
        assert isinstance(device, WasserleserDevice)
        return self.entity_description.value_fn(device)


class WaermeleserSensor(_EnergieleserSensorBase):
    """Sensor entity for a wärmeleser device."""

    entity_description: WaermeleserSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        device = self.coordinator.data
        assert isinstance(device, WaermeleserDevice)
        return self.entity_description.value_fn(device)
