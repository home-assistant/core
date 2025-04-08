"""Constants used by the SmartThings component and platforms."""

from pysmartthings import Attribute, Capability, Category

DOMAIN = "smartthings"

SCOPES = [
    "r:devices:*",
    "w:devices:*",
    "x:devices:*",
    "r:hubs:*",
    "r:locations:*",
    "w:locations:*",
    "x:locations:*",
    "r:scenes:*",
    "x:scenes:*",
    "r:rules:*",
    "w:rules:*",
    "sse",
]

REQUESTED_SCOPES = [
    *SCOPES,
    "r:installedapps",
    "w:installedapps",
]

CONF_APP_ID = "app_id"
CONF_CLOUDHOOK_URL = "cloudhook_url"
CONF_INSTALLED_APP_ID = "installed_app_id"
CONF_INSTANCE_ID = "instance_id"
CONF_LOCATION_ID = "location_id"
CONF_REFRESH_TOKEN = "refresh_token"

MAIN = "main"
OLD_DATA = "old_data"

CONF_SUBSCRIPTION_ID = "subscription_id"
EVENT_BUTTON = "smartthings.button"

BINARY_SENSOR_ATTRIBUTES_TO_CAPABILITIES: dict[str, str] = {
    Attribute.ACCELERATION: Capability.ACCELERATION_SENSOR,
    Attribute.CONTACT: Capability.CONTACT_SENSOR,
    Attribute.FILTER_STATUS: Capability.FILTER_STATUS,
    Attribute.MOTION: Capability.MOTION_SENSOR,
    Attribute.PRESENCE: Capability.PRESENCE_SENSOR,
    Attribute.SOUND: Capability.SOUND_SENSOR,
    Attribute.TAMPER: Capability.TAMPER_ALERT,
    Attribute.VALVE: Capability.VALVE,
    Attribute.WATER: Capability.WATER_SENSOR,
}

SENSOR_ATTRIBUTES_TO_CAPABILITIES: dict[str, str] = {
    Attribute.LIGHTING_MODE: Capability.ACTIVITY_LIGHTING_MODE,
    Attribute.AIR_CONDITIONER_MODE: Capability.AIR_CONDITIONER_MODE,
    Attribute.AIR_QUALITY: Capability.AIR_QUALITY_SENSOR,
    Attribute.ALARM: Capability.ALARM,
    Attribute.BATTERY: Capability.BATTERY,
    Attribute.BMI_MEASUREMENT: Capability.BODY_MASS_INDEX_MEASUREMENT,
    Attribute.BODY_WEIGHT_MEASUREMENT: Capability.BODY_WEIGHT_MEASUREMENT,
    Attribute.CARBON_DIOXIDE: Capability.CARBON_DIOXIDE_MEASUREMENT,
    Attribute.CARBON_MONOXIDE: Capability.CARBON_MONOXIDE_MEASUREMENT,
    Attribute.CARBON_MONOXIDE_LEVEL: Capability.CARBON_MONOXIDE_MEASUREMENT,
    Attribute.DISHWASHER_JOB_STATE: Capability.DISHWASHER_OPERATING_STATE,
    Attribute.DRYER_MODE: Capability.DRYER_MODE,
    Attribute.DRYER_JOB_STATE: Capability.DRYER_OPERATING_STATE,
    Attribute.DUST_LEVEL: Capability.DUST_SENSOR,
    Attribute.FINE_DUST_LEVEL: Capability.DUST_SENSOR,
    Attribute.ENERGY: Capability.ENERGY_METER,
    Attribute.EQUIVALENT_CARBON_DIOXIDE_MEASUREMENT: Capability.EQUIVALENT_CARBON_DIOXIDE_MEASUREMENT,
    Attribute.FORMALDEHYDE_LEVEL: Capability.FORMALDEHYDE_MEASUREMENT,
    Attribute.GAS_METER: Capability.GAS_METER,
    Attribute.GAS_METER_CALORIFIC: Capability.GAS_METER,
    Attribute.GAS_METER_TIME: Capability.GAS_METER,
    Attribute.GAS_METER_VOLUME: Capability.GAS_METER,
    Attribute.ILLUMINANCE: Capability.ILLUMINANCE_MEASUREMENT,
    Attribute.INFRARED_LEVEL: Capability.INFRARED_LEVEL,
    Attribute.INPUT_SOURCE: Capability.MEDIA_INPUT_SOURCE,
    Attribute.PLAYBACK_REPEAT_MODE: Capability.MEDIA_PLAYBACK_REPEAT,
    Attribute.PLAYBACK_SHUFFLE: Capability.MEDIA_PLAYBACK_SHUFFLE,
    Attribute.PLAYBACK_STATUS: Capability.MEDIA_PLAYBACK,
    Attribute.ODOR_LEVEL: Capability.ODOR_SENSOR,
    Attribute.OVEN_MODE: Capability.OVEN_MODE,
    Attribute.OVEN_JOB_STATE: Capability.OVEN_OPERATING_STATE,
    Attribute.OVEN_SETPOINT: Capability.OVEN_SETPOINT,
    Attribute.POWER: Capability.POWER_METER,
    Attribute.POWER_SOURCE: Capability.POWER_SOURCE,
    Attribute.REFRIGERATION_SETPOINT: Capability.REFRIGERATION_SETPOINT,
    Attribute.HUMIDITY: Capability.RELATIVE_HUMIDITY_MEASUREMENT,
    Attribute.ROBOT_CLEANER_CLEANING_MODE: Capability.ROBOT_CLEANER_CLEANING_MODE,
    Attribute.ROBOT_CLEANER_MOVEMENT: Capability.ROBOT_CLEANER_MOVEMENT,
    Attribute.ROBOT_CLEANER_TURBO_MODE: Capability.ROBOT_CLEANER_TURBO_MODE,
    Attribute.LQI: Capability.SIGNAL_STRENGTH,
    Attribute.RSSI: Capability.SIGNAL_STRENGTH,
    Attribute.SMOKE: Capability.SMOKE_DETECTOR,
    Attribute.TEMPERATURE: Capability.TEMPERATURE_MEASUREMENT,
    Attribute.COOLING_SETPOINT: Capability.THERMOSTAT_COOLING_SETPOINT,
    Attribute.THERMOSTAT_FAN_MODE: Capability.THERMOSTAT_FAN_MODE,
    Attribute.HEATING_SETPOINT: Capability.THERMOSTAT_HEATING_SETPOINT,
    Attribute.THERMOSTAT_MODE: Capability.THERMOSTAT_MODE,
    Attribute.THERMOSTAT_OPERATING_STATE: Capability.THERMOSTAT_OPERATING_STATE,
    Attribute.THERMOSTAT_SETPOINT: Capability.THERMOSTAT_SETPOINT,
    Attribute.TV_CHANNEL: Capability.TV_CHANNEL,
    Attribute.TV_CHANNEL_NAME: Capability.TV_CHANNEL,
    Attribute.TVOC_LEVEL: Capability.TVOC_MEASUREMENT,
    Attribute.ULTRAVIOLET_INDEX: Capability.ULTRAVIOLET_INDEX,
    Attribute.VERY_FINE_DUST_LEVEL: Capability.VERY_FINE_DUST_SENSOR,
    Attribute.VOLTAGE: Capability.VOLTAGE_MEASUREMENT,
    Attribute.WASHER_MODE: Capability.WASHER_MODE,
    Attribute.WASHER_JOB_STATE: Capability.WASHER_OPERATING_STATE,
}

INVALID_SWITCH_CATEGORIES = {
    Category.CLOTHING_CARE_MACHINE,
    Category.COOKTOP,
    Category.DRYER,
    Category.WASHER,
    Category.MICROWAVE,
    Category.DISHWASHER,
}
