"""Constants for the Renson integration."""
from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.sensor import (
    STATE_CLASS_MEASUREMENT,
    SensorEntityDescription,
)
from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TIMESTAMP,
    TEMP_CELSIUS,
)

DOMAIN = "renson"
CONCENTRATION_PARTS_PER_CUBIC_METER = "ppm"

CO2_QUALITY_DESC = SensorEntityDescription(
    key="CO2_QUALITY_FIELD", name="CO2 quality", state_class=STATE_CLASS_MEASUREMENT
)

CO2_DESC = SensorEntityDescription(
    key="CO2_FIELD",
    name="CO2 quality value",
    device_class="carbon_dioxide",
    state_class=STATE_CLASS_MEASUREMENT,
    native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
)

AIR_QUALITY_DESC = SensorEntityDescription(
    key="AIR_QUALITY_FIELD", name="Air quality", state_class=STATE_CLASS_MEASUREMENT
)

AIR_DESC = SensorEntityDescription(
    key="AIR_FIELD",
    name="Air quality value",
    state_class=STATE_CLASS_MEASUREMENT,
    native_unit_of_measurement=CONCENTRATION_PARTS_PER_CUBIC_METER,
)

CURRENT_LEVEL_RAW_DESC = SensorEntityDescription(
    key="CURRENT_LEVEL_FIELD_RAW",
    name="Ventilation level raw",
    state_class=STATE_CLASS_MEASUREMENT,
)

CURRENT_LEVEL_DESC = SensorEntityDescription(
    key="CURRENT_LEVEL_FIELD",
    name="Ventilation level",
    state_class=STATE_CLASS_MEASUREMENT,
)

CURRENT_AIRFLOW_EXTRACT_DESC = SensorEntityDescription(
    key="CURRENT_AIRFLOW_EXTRACT_FIELD",
    name="Total airflow out",
    state_class=STATE_CLASS_MEASUREMENT,
    native_unit_of_measurement="m³/h",
)

CURRENT_AIRFLOW_INGOING_DESC = SensorEntityDescription(
    key="CURRENT_AIRFLOW_INGOING_FIELD",
    name="Total airflow int",
    state_class=STATE_CLASS_MEASUREMENT,
    native_unit_of_measurement="m³/h",
)

OUTDOOR_TEMP_DESC = SensorEntityDescription(
    key="OUTDOOR_TEMP_FIELD",
    name="Outdoor air temperature",
    device_class="temperature",
    state_class=STATE_CLASS_MEASUREMENT,
    native_unit_of_measurement=TEMP_CELSIUS,
)

INDOOR_TEMP_DESC = SensorEntityDescription(
    key="INDOOR_TEMP_FIELD",
    name="Extract air temperature",
    device_class="temperature",
    state_class=STATE_CLASS_MEASUREMENT,
    native_unit_of_measurement=TEMP_CELSIUS,
)

FILTER_REMAIN_DESC = SensorEntityDescription(
    key="FILTER_REMAIN_FIELD",
    name="Filter change",
    state_class=STATE_CLASS_MEASUREMENT,
    native_unit_of_measurement="days",
)

HUMIDITY_DESC = SensorEntityDescription(
    key="HUMIDITY_FIELD",
    name="Relative humidity",
    device_class=DEVICE_CLASS_HUMIDITY,
    state_class=STATE_CLASS_MEASUREMENT,
    native_unit_of_measurement="%",
)

MANUAL_LEVEL_DESC = SensorEntityDescription(
    key="MANUAL_LEVEL_FIELD",
    name="Manual level",
    state_class=STATE_CLASS_MEASUREMENT,
)

TIME_AND_DATE_DESC = SensorEntityDescription(
    key="MANUAL_LEVEL_FIELD",
    name="System time",
    device_class=DEVICE_CLASS_TIMESTAMP,
    state_class=STATE_CLASS_MEASUREMENT,
)

BREEZE_TEMPERATURE_DESC = SensorEntityDescription(
    key="BREEZE_TEMPERATURE_FIELD",
    name="Breeze temperature",
    device_class=TEMP_CELSIUS,
    state_class=STATE_CLASS_MEASUREMENT,
    native_unit_of_measurement=TEMP_CELSIUS,
)

BREEZE_LEVEL_DESC = SensorEntityDescription(
    key="BREEZE_LEVEL_FIELD",
    name="Breeze level",
    state_class=STATE_CLASS_MEASUREMENT,
)

DAYTIME_DESC = SensorEntityDescription(
    key="DAYTIME_FIELD",
    name="Start day time",
    state_class=STATE_CLASS_MEASUREMENT,
)


NIGHTTIME_DESC = SensorEntityDescription(
    key="NIGHTTIME_FIELD",
    name="Start night time",
    state_class=STATE_CLASS_MEASUREMENT,
)

DAY_POLLUTION_DESC = SensorEntityDescription(
    key="DAY_POLLUTION_FIELD",
    name="Day pollution level",
    state_class=STATE_CLASS_MEASUREMENT,
)

NIGHT_POLLUTION_DESC = SensorEntityDescription(
    key="NIGHT_POLLUTION_FIELD",
    name="Night pollution level",
    state_class=STATE_CLASS_MEASUREMENT,
)

CO2_THRESHOLD_DESC = SensorEntityDescription(
    key="CO2_THRESHOLD_FIELD",
    name="CO2 threshold",
    state_class=STATE_CLASS_MEASUREMENT,
    native_unit_of_measurement="ppm",
)

CO2_HYSTERESIS_DESC = SensorEntityDescription(
    key="CO2_HYSTERESIS_FIELD",
    name="CO2 hysteresis",
    state_class=STATE_CLASS_MEASUREMENT,
    native_unit_of_measurement="ppm",
)

BYPASS_TEMPERATURE_DESC = SensorEntityDescription(
    key="BYPASS_TEMPERATURE_FIELD",
    name="Bypass activation temperature",
    device_class="temperature",
    state_class=STATE_CLASS_MEASUREMENT,
    native_unit_of_measurement=TEMP_CELSIUS,
)

BYPASS_LEVEL_DESC = SensorEntityDescription(
    key="BYPASS_LEVEL_FIELD",
    name="Bypass level",
    device_class="power_factor",
    state_class=STATE_CLASS_MEASUREMENT,
    native_unit_of_measurement="%",
)

FILTER_PRESET_DESC = SensorEntityDescription(
    key="FILTER_PRESET_FIELD",
    name="Filter preset time",
    state_class=STATE_CLASS_MEASUREMENT,
    native_unit_of_measurement="days",
)

PREHEATER_DESC = BinarySensorEntityDescription(
    key="PREHEATER_FIELD",
    name="Preheater enabled",
)

HUMIDITY_CONTROL_DESC = BinarySensorEntityDescription(
    key="HUMIDITY_CONTROL_FIELD",
    name="Humidity control enabled",
)

AIR_QUALITY_CONTROL_DESC = BinarySensorEntityDescription(
    key="AIR_QUALITY_CONTROL_FIELD",
    name="Air quality control enabled",
)

CO2_CONTROL_DESC = BinarySensorEntityDescription(
    key="CO2_CONTROL_FIELD",
    name="CO2 control enabled",
)

FROST_PROTECTION_DESC = BinarySensorEntityDescription(
    key="FROST_PROTECTION_FIELD",
    name="Frost protection active",
)

BREEZE_ENABLE_DESC = BinarySensorEntityDescription(
    key="BREEZE_ENABLE_FIELD",
    name="Breeze enabled",
)

BREEZE_MET_DESC = BinarySensorEntityDescription(
    key="BREEZE_MET_FIELD",
    name="Breeze conditions met",
)
