"""Constants for the Landis+Gyr Heat Meter integration."""

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
    UnitOfVolume,
    UnitOfVolumeFlowRate,
)

DOMAIN = "landisgyr_heat_meter"

GJ_TO_MWH = 0.277778  # conversion factor
ULTRAHEAT_TIMEOUT = 30  # reading the IR port can take some time

HEAT_METER_SENSOR_TYPES = (
    SensorEntityDescription(
        key="heat_usage",
        icon="mdi:fire",
        name="Heat usage",
        native_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
    ),
    SensorEntityDescription(
        key="volume_usage_m3",
        icon="mdi:fire",
        name="Volume usage",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        state_class=SensorStateClass.TOTAL,
    ),
    # Diagnostic entity for debugging, this will match the value in GJ indicated on the meter's display
    SensorEntityDescription(
        key="heat_usage_gj",
        icon="mdi:fire",
        name="Heat usage GJ",
        native_unit_of_measurement="GJ",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="heat_previous_year",
        icon="mdi:fire",
        name="Heat usage previous year",
        native_unit_of_measurement=UnitOfEnergy.MEGA_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    # Diagnostic entity for debugging, this will match the value in GJ of previous year indicated on the meter's display
    SensorEntityDescription(
        key="heat_previous_year_gj",
        icon="mdi:fire",
        name="Heat previous year GJ",
        native_unit_of_measurement="GJ",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="volume_previous_year_m3",
        icon="mdi:fire",
        name="Volume usage previous year",
        device_class=SensorDeviceClass.VOLUME,
        native_unit_of_measurement=UnitOfVolume.CUBIC_METERS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="ownership_number",
        name="Ownership number",
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="error_number",
        name="Error number",
        icon="mdi:home-alert",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="device_number",
        name="Device number",
        icon="mdi:identifier",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="measurement_period_minutes",
        name="Measurement period minutes",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="power_max_kw",
        name="Power max",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="power_max_previous_year_kw",
        name="Power max previous year",
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        device_class=SensorDeviceClass.POWER,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="flowrate_max_m3ph",
        name="Flowrate max",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        icon="mdi:water-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="flowrate_max_previous_year_m3ph",
        name="Flowrate max previous year",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        icon="mdi:water-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="return_temperature_max_c",
        name="Return temperature max",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="return_temperature_max_previous_year_c",
        name="Return temperature max previous year",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="flow_temperature_max_c",
        name="Flow temperature max",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="flow_temperature_max_previous_year_c",
        name="Flow temperature max previous year",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="operating_hours",
        name="Operating hours",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="flow_hours",
        name="Flow hours",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="fault_hours",
        name="Fault hours",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="fault_hours_previous_year",
        name="Fault hours previous year",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="yearly_set_day",
        name="Yearly set day",
        icon="mdi:clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="monthly_set_day",
        name="Monthly set day",
        icon="mdi:clock-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="meter_date_time",
        name="Meter date time",
        icon="mdi:clock-outline",
        device_class=SensorDeviceClass.TIMESTAMP,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="measuring_range_m3ph",
        name="Measuring range",
        native_unit_of_measurement=UnitOfVolumeFlowRate.CUBIC_METERS_PER_HOUR,
        icon="mdi:water-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    SensorEntityDescription(
        key="settings_and_firmware",
        name="Settings and firmware",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)
