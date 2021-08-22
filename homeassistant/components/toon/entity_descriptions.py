"""Entity descriptions for Toon entities."""
from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_CONNECTIVITY,
    DEVICE_CLASS_PROBLEM,
    BinarySensorEntityDescription,
)
from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    STATE_CLASS_TOTAL_INCREASING,
    SensorEntityDescription,
)
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.const import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_GAS,
    DEVICE_CLASS_POWER,
    DEVICE_CLASS_TEMPERATURE,
    ENERGY_KILO_WATT_HOUR,
    PERCENTAGE,
    POWER_WATT,
    TEMP_CELSIUS,
    VOLUME_CUBIC_METERS,
)

from .binary_sensor import (
    ToonBinarySensor,
    ToonBoilerBinarySensor,
    ToonBoilerModuleBinarySensor,
    ToonDisplayBinarySensor,
)
from .const import ATTR_MEASUREMENT, CURRENCY_EUR, VOLUME_CM3, VOLUME_LMIN
from .sensor import (
    ToonBoilerDeviceSensor,
    ToonDisplayDeviceSensor,
    ToonElectricityMeterDeviceSensor,
    ToonGasMeterDeviceSensor,
    ToonSensor,
    ToonSolarDeviceSensor,
    ToonWaterMeterDeviceSensor,
)
from .switch import ToonHolidayModeSwitch, ToonProgramSwitch, ToonSwitch


@dataclass
class ToonRequiredKeysMixin:
    """Mixin for required keys."""

    section: str
    measurement: str


@dataclass
class ToonBinarySensorRequiredKeysMixin(ToonRequiredKeysMixin):
    """Mixin for binary sensor required keys."""

    cls: type[ToonBinarySensor]


@dataclass
class ToonBinarySensorEntityDescription(
    BinarySensorEntityDescription, ToonBinarySensorRequiredKeysMixin
):
    """Describes Toon binary sensor entity."""

    inverted: bool = False


BINARY_SENSOR_ENTITIES = (
    ToonBinarySensorEntityDescription(
        key="thermostat_info_boiler_connected_None",
        name="Boiler Module Connection",
        section="thermostat",
        measurement="boiler_module_connected",
        device_class=DEVICE_CLASS_CONNECTIVITY,
        entity_registry_enabled_default=False,
        cls=ToonBoilerModuleBinarySensor,
    ),
    ToonBinarySensorEntityDescription(
        key="thermostat_program_overridden",
        name="Thermostat Program Override",
        section="thermostat",
        measurement="program_overridden",
        icon="mdi:gesture-tap",
        cls=ToonDisplayBinarySensor,
    ),
)

BINARY_SENSOR_ENTITIES_BOILER: tuple[ToonBinarySensorEntityDescription, ...] = (
    ToonBinarySensorEntityDescription(
        key="thermostat_info_burner_info_1",
        name="Boiler Heating",
        section="thermostat",
        measurement="heating",
        icon="mdi:fire",
        entity_registry_enabled_default=False,
        cls=ToonBoilerBinarySensor,
    ),
    ToonBinarySensorEntityDescription(
        key="thermostat_info_burner_info_2",
        name="Hot Tap Water",
        section="thermostat",
        measurement="hot_tapwater",
        icon="mdi:water-pump",
        cls=ToonBoilerBinarySensor,
    ),
    ToonBinarySensorEntityDescription(
        key="thermostat_info_burner_info_3",
        name="Boiler Preheating",
        section="thermostat",
        measurement="pre_heating",
        icon="mdi:fire",
        entity_registry_enabled_default=False,
        cls=ToonBoilerBinarySensor,
    ),
    ToonBinarySensorEntityDescription(
        key="thermostat_info_burner_info_None",
        name="Boiler Burner",
        section="thermostat",
        measurement="burner",
        icon="mdi:fire",
        cls=ToonBoilerBinarySensor,
    ),
    ToonBinarySensorEntityDescription(
        key="thermostat_info_error_found_255",
        name="Boiler Status",
        section="thermostat",
        measurement="error_found",
        device_class=DEVICE_CLASS_PROBLEM,
        icon="mdi:alert",
        cls=ToonBoilerBinarySensor,
    ),
    ToonBinarySensorEntityDescription(
        key="thermostat_info_ot_communication_error_0",
        name="OpenTherm Connection",
        section="thermostat",
        measurement="opentherm_communication_error",
        device_class=DEVICE_CLASS_PROBLEM,
        icon="mdi:check-network-outline",
        entity_registry_enabled_default=False,
        cls=ToonBoilerBinarySensor,
    ),
)


@dataclass
class ToonSensorRequiredKeysMixin(ToonRequiredKeysMixin):
    """Mixin for sensor required keys."""

    cls: type[ToonSensor]


@dataclass
class ToonSensorEntityDescription(SensorEntityDescription, ToonSensorRequiredKeysMixin):
    """Describes Toon sensor entity."""


SENSOR_ENTITIES: tuple[ToonSensorEntityDescription, ...] = (
    ToonSensorEntityDescription(
        key="current_display_temperature",
        name="Temperature",
        section="thermostat",
        measurement="current_display_temperature",
        native_unit_of_measurement=TEMP_CELSIUS,
        device_class=DEVICE_CLASS_TEMPERATURE,
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
        cls=ToonDisplayDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="gas_average",
        name="Average Gas Usage",
        section="gas_usage",
        measurement="average",
        native_unit_of_measurement=VOLUME_CM3,
        icon="mdi:gas-cylinder",
        cls=ToonGasMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="gas_average_daily",
        name="Average Daily Gas Usage",
        section="gas_usage",
        measurement="day_average",
        device_class=DEVICE_CLASS_GAS,
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        entity_registry_enabled_default=False,
        cls=ToonGasMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="gas_daily_usage",
        name="Gas Usage Today",
        section="gas_usage",
        measurement="day_usage",
        device_class=DEVICE_CLASS_GAS,
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        cls=ToonGasMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="gas_daily_cost",
        name="Gas Cost Today",
        section="gas_usage",
        measurement="day_cost",
        native_unit_of_measurement=CURRENCY_EUR,
        icon="mdi:gas-cylinder",
        cls=ToonGasMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="gas_meter_reading",
        name="Gas Meter",
        section="gas_usage",
        measurement="meter",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        device_class=DEVICE_CLASS_GAS,
        entity_registry_enabled_default=False,
        cls=ToonGasMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="gas_value",
        name="Current Gas Usage",
        section="gas_usage",
        measurement="current",
        native_unit_of_measurement=VOLUME_CM3,
        icon="mdi:gas-cylinder",
        cls=ToonGasMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_average",
        name="Average Power Usage",
        section="power_usage",
        measurement="average",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        entity_registry_enabled_default=False,
        cls=ToonElectricityMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_average_daily",
        name="Average Daily Energy Usage",
        section="power_usage",
        measurement="day_average",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        entity_registry_enabled_default=False,
        cls=ToonElectricityMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_daily_cost",
        name="Energy Cost Today",
        section="power_usage",
        measurement="day_cost",
        native_unit_of_measurement=CURRENCY_EUR,
        icon="mdi:power-plug",
        cls=ToonElectricityMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_daily_value",
        name="Energy Usage Today",
        section="power_usage",
        measurement="day_usage",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        cls=ToonElectricityMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_meter_reading",
        name="Electricity Meter Feed IN Tariff 1",
        section="power_usage",
        measurement="meter_high",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        cls=ToonElectricityMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_meter_reading_low",
        name="Electricity Meter Feed IN Tariff 2",
        section="power_usage",
        measurement="meter_low",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        cls=ToonElectricityMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_value",
        name="Current Power Usage",
        section="power_usage",
        measurement="current",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        cls=ToonElectricityMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="solar_meter_reading_produced",
        name="Electricity Meter Feed OUT Tariff 1",
        section="power_usage",
        measurement="meter_produced_high",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        cls=ToonElectricityMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="solar_meter_reading_low_produced",
        name="Electricity Meter Feed OUT Tariff 2",
        section="power_usage",
        measurement="meter_produced_low",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        entity_registry_enabled_default=False,
        cls=ToonElectricityMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="water_average",
        name="Average Water Usage",
        section="water_usage",
        measurement="average",
        native_unit_of_measurement=VOLUME_LMIN,
        icon="mdi:water",
        entity_registry_enabled_default=False,
        cls=ToonWaterMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="water_average_daily",
        name="Average Daily Water Usage",
        section="water_usage",
        measurement="day_average",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        icon="mdi:water",
        entity_registry_enabled_default=False,
        cls=ToonWaterMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="water_daily_usage",
        name="Water Usage Today",
        section="water_usage",
        measurement="day_usage",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        icon="mdi:water",
        entity_registry_enabled_default=False,
        cls=ToonWaterMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="water_meter_reading",
        name="Water Meter",
        section="water_usage",
        measurement="meter",
        native_unit_of_measurement=VOLUME_CUBIC_METERS,
        icon="mdi:water",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_TOTAL_INCREASING,
        cls=ToonWaterMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="water_value",
        name="Current Water Usage",
        section="water_usage",
        measurement="current",
        native_unit_of_measurement=VOLUME_LMIN,
        icon="mdi:water-pump",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
        cls=ToonWaterMeterDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="water_daily_cost",
        name="Water Cost Today",
        section="water_usage",
        measurement="day_cost",
        native_unit_of_measurement=CURRENCY_EUR,
        icon="mdi:water-pump",
        entity_registry_enabled_default=False,
        cls=ToonWaterMeterDeviceSensor,
    ),
)

SENSOR_ENTITIES_SOLAR: tuple[ToonSensorEntityDescription, ...] = (
    ToonSensorEntityDescription(
        key="solar_value",
        name="Current Solar Power Production",
        section="power_usage",
        measurement="current_solar",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=STATE_CLASS_MEASUREMENT,
        cls=ToonSolarDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="solar_maximum",
        name="Max Solar Power Production Today",
        section="power_usage",
        measurement="day_max_solar",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        cls=ToonSolarDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="solar_produced",
        name="Solar Power Production to Grid",
        section="power_usage",
        measurement="current_produced",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        state_class=ATTR_MEASUREMENT,
        cls=ToonSolarDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_usage_day_produced_solar",
        name="Solar Energy Produced Today",
        section="power_usage",
        measurement="day_produced_solar",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        cls=ToonSolarDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_usage_day_to_grid_usage",
        name="Energy Produced To Grid Today",
        section="power_usage",
        measurement="day_to_grid_usage",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        entity_registry_enabled_default=False,
        cls=ToonSolarDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_usage_day_from_grid_usage",
        name="Energy Usage From Grid Today",
        section="power_usage",
        measurement="day_from_grid_usage",
        native_unit_of_measurement=ENERGY_KILO_WATT_HOUR,
        device_class=DEVICE_CLASS_ENERGY,
        entity_registry_enabled_default=False,
        cls=ToonSolarDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="solar_average_produced",
        name="Average Solar Power Production to Grid",
        section="power_usage",
        measurement="average_produced",
        native_unit_of_measurement=POWER_WATT,
        device_class=DEVICE_CLASS_POWER,
        entity_registry_enabled_default=False,
        cls=ToonSolarDeviceSensor,
    ),
    ToonSensorEntityDescription(
        key="power_usage_current_covered_by_solar",
        name="Current Power Usage Covered By Solar",
        section="power_usage",
        measurement="current_covered_by_solar",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:solar-power",
        state_class=STATE_CLASS_MEASUREMENT,
        cls=ToonSolarDeviceSensor,
    ),
)

SENSOR_ENTITIES_BOILER: tuple[ToonSensorEntityDescription, ...] = (
    ToonSensorEntityDescription(
        key="thermostat_info_current_modulation_level",
        name="Boiler Modulation Level",
        section="thermostat",
        measurement="current_modulation_level",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:percent",
        entity_registry_enabled_default=False,
        state_class=STATE_CLASS_MEASUREMENT,
        cls=ToonBoilerDeviceSensor,
    ),
)


@dataclass
class ToonSwitchRequiredKeysMixin(ToonRequiredKeysMixin):
    """Mixin for switch required keys."""

    cls: type[ToonSwitch]


@dataclass
class ToonSwitchEntityDescription(SwitchEntityDescription, ToonSwitchRequiredKeysMixin):
    """Describes Toon switch entity."""


SWITCH_ENTITIES: tuple[ToonSwitchEntityDescription, ...] = (
    ToonSwitchEntityDescription(
        key="thermostat_holiday_mode",
        name="Holiday Mode",
        section="thermostat",
        measurement="holiday_mode",
        icon="mdi:airport",
        cls=ToonHolidayModeSwitch,
    ),
    ToonSwitchEntityDescription(
        key="thermostat_program",
        name="Thermostat Program",
        section="thermostat",
        measurement="program",
        icon="mdi:calendar-clock",
        cls=ToonProgramSwitch,
    ),
)
