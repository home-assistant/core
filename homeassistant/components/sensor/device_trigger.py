"""Provides device triggers for sensors."""

import voluptuous as vol

from homeassistant.components.device_automation import (
    DEVICE_TRIGGER_BASE_SCHEMA,
    InvalidDeviceAutomationConfig,
    async_get_entity_registry_entry_or_raise,
)
from homeassistant.components.homeassistant.triggers import (
    numeric_state as numeric_state_trigger,
)
from homeassistant.const import (
    CONF_ABOVE,
    CONF_BELOW,
    CONF_ENTITY_ID,
    CONF_FOR,
    CONF_TYPE,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.entity import (
    get_capability,
    get_device_class,
    get_unit_of_measurement,
)
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from . import ATTR_STATE_CLASS, DOMAIN, SensorDeviceClass

DEVICE_CLASS_NONE = "none"

CONF_APPARENT_POWER = "apparent_power"
CONF_AQI = "aqi"
CONF_AREA = "area"
CONF_ATMOSPHERIC_PRESSURE = "atmospheric_pressure"
CONF_BATTERY_LEVEL = "battery_level"
CONF_BLOOD_GLUCOSE_CONCENTRATION = "blood_glucose_concentration"
CONF_CO = "carbon_monoxide"
CONF_CO2 = "carbon_dioxide"
CONF_CONDUCTIVITY = "conductivity"
CONF_CURRENT = "current"
CONF_DATA_RATE = "data_rate"
CONF_DATA_SIZE = "data_size"
CONF_DISTANCE = "distance"
CONF_DURATION = "duration"
CONF_ENERGY = "energy"
CONF_ENERGY_DISTANCE = "energy_distance"
CONF_FREQUENCY = "frequency"
CONF_GAS = "gas"
CONF_HUMIDITY = "humidity"
CONF_ILLUMINANCE = "illuminance"
CONF_IRRADIANCE = "irradiance"
CONF_MOISTURE = "moisture"
CONF_MONETARY = "monetary"
CONF_NITROGEN_DIOXIDE = "nitrogen_dioxide"
CONF_NITROGEN_MONOXIDE = "nitrogen_monoxide"
CONF_NITROUS_OXIDE = "nitrous_oxide"
CONF_OZONE = "ozone"
CONF_PH = "ph"
CONF_PM1 = "pm1"
CONF_PM10 = "pm10"
CONF_PM25 = "pm25"
CONF_POWER = "power"
CONF_POWER_FACTOR = "power_factor"
CONF_PRECIPITATION = "precipitation"
CONF_PRECIPITATION_INTENSITY = "precipitation_intensity"
CONF_PRESSURE = "pressure"
CONF_REACTIVE_POWER = "reactive_power"
CONF_SIGNAL_STRENGTH = "signal_strength"
CONF_SOUND_PRESSURE = "sound_pressure"
CONF_SPEED = "speed"
CONF_SULPHUR_DIOXIDE = "sulphur_dioxide"
CONF_TEMPERATURE = "temperature"
CONF_VALUE = "value"
CONF_VOLATILE_ORGANIC_COMPOUNDS = "volatile_organic_compounds"
CONF_VOLATILE_ORGANIC_COMPOUNDS_PARTS = "volatile_organic_compounds_parts"
CONF_VOLTAGE = "voltage"
CONF_VOLUME = "volume"
CONF_VOLUME_FLOW_RATE = "volume_flow_rate"
CONF_WATER = "water"
CONF_WEIGHT = "weight"
CONF_WIND_DIRECTION = "wind_direction"
CONF_WIND_SPEED = "wind_speed"

ENTITY_TRIGGERS = {
    SensorDeviceClass.APPARENT_POWER: [{CONF_TYPE: CONF_APPARENT_POWER}],
    SensorDeviceClass.AQI: [{CONF_TYPE: CONF_AQI}],
    SensorDeviceClass.AREA: [{CONF_TYPE: CONF_AREA}],
    SensorDeviceClass.ATMOSPHERIC_PRESSURE: [{CONF_TYPE: CONF_ATMOSPHERIC_PRESSURE}],
    SensorDeviceClass.BATTERY: [{CONF_TYPE: CONF_BATTERY_LEVEL}],
    SensorDeviceClass.BLOOD_GLUCOSE_CONCENTRATION: [
        {CONF_TYPE: CONF_BLOOD_GLUCOSE_CONCENTRATION}
    ],
    SensorDeviceClass.CO: [{CONF_TYPE: CONF_CO}],
    SensorDeviceClass.CO2: [{CONF_TYPE: CONF_CO2}],
    SensorDeviceClass.CONDUCTIVITY: [{CONF_TYPE: CONF_CONDUCTIVITY}],
    SensorDeviceClass.CURRENT: [{CONF_TYPE: CONF_CURRENT}],
    SensorDeviceClass.DATA_RATE: [{CONF_TYPE: CONF_DATA_RATE}],
    SensorDeviceClass.DATA_SIZE: [{CONF_TYPE: CONF_DATA_SIZE}],
    SensorDeviceClass.DISTANCE: [{CONF_TYPE: CONF_DISTANCE}],
    SensorDeviceClass.DURATION: [{CONF_TYPE: CONF_DURATION}],
    SensorDeviceClass.ENERGY: [{CONF_TYPE: CONF_ENERGY}],
    SensorDeviceClass.ENERGY_DISTANCE: [{CONF_TYPE: CONF_ENERGY_DISTANCE}],
    SensorDeviceClass.ENERGY_STORAGE: [{CONF_TYPE: CONF_ENERGY}],
    SensorDeviceClass.FREQUENCY: [{CONF_TYPE: CONF_FREQUENCY}],
    SensorDeviceClass.GAS: [{CONF_TYPE: CONF_GAS}],
    SensorDeviceClass.HUMIDITY: [{CONF_TYPE: CONF_HUMIDITY}],
    SensorDeviceClass.ILLUMINANCE: [{CONF_TYPE: CONF_ILLUMINANCE}],
    SensorDeviceClass.IRRADIANCE: [{CONF_TYPE: CONF_IRRADIANCE}],
    SensorDeviceClass.MOISTURE: [{CONF_TYPE: CONF_MOISTURE}],
    SensorDeviceClass.MONETARY: [{CONF_TYPE: CONF_MONETARY}],
    SensorDeviceClass.NITROGEN_DIOXIDE: [{CONF_TYPE: CONF_NITROGEN_DIOXIDE}],
    SensorDeviceClass.NITROGEN_MONOXIDE: [{CONF_TYPE: CONF_NITROGEN_MONOXIDE}],
    SensorDeviceClass.NITROUS_OXIDE: [{CONF_TYPE: CONF_NITROUS_OXIDE}],
    SensorDeviceClass.OZONE: [{CONF_TYPE: CONF_OZONE}],
    SensorDeviceClass.PH: [{CONF_TYPE: CONF_PH}],
    SensorDeviceClass.PM1: [{CONF_TYPE: CONF_PM1}],
    SensorDeviceClass.PM10: [{CONF_TYPE: CONF_PM10}],
    SensorDeviceClass.PM25: [{CONF_TYPE: CONF_PM25}],
    SensorDeviceClass.POWER: [{CONF_TYPE: CONF_POWER}],
    SensorDeviceClass.POWER_FACTOR: [{CONF_TYPE: CONF_POWER_FACTOR}],
    SensorDeviceClass.PRECIPITATION: [{CONF_TYPE: CONF_PRECIPITATION}],
    SensorDeviceClass.PRECIPITATION_INTENSITY: [
        {CONF_TYPE: CONF_PRECIPITATION_INTENSITY}
    ],
    SensorDeviceClass.PRESSURE: [{CONF_TYPE: CONF_PRESSURE}],
    SensorDeviceClass.REACTIVE_POWER: [{CONF_TYPE: CONF_REACTIVE_POWER}],
    SensorDeviceClass.SIGNAL_STRENGTH: [{CONF_TYPE: CONF_SIGNAL_STRENGTH}],
    SensorDeviceClass.SOUND_PRESSURE: [{CONF_TYPE: CONF_SOUND_PRESSURE}],
    SensorDeviceClass.SPEED: [{CONF_TYPE: CONF_SPEED}],
    SensorDeviceClass.SULPHUR_DIOXIDE: [{CONF_TYPE: CONF_SULPHUR_DIOXIDE}],
    SensorDeviceClass.TEMPERATURE: [{CONF_TYPE: CONF_TEMPERATURE}],
    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS: [
        {CONF_TYPE: CONF_VOLATILE_ORGANIC_COMPOUNDS}
    ],
    SensorDeviceClass.VOLATILE_ORGANIC_COMPOUNDS_PARTS: [
        {CONF_TYPE: CONF_VOLATILE_ORGANIC_COMPOUNDS_PARTS}
    ],
    SensorDeviceClass.VOLTAGE: [{CONF_TYPE: CONF_VOLTAGE}],
    SensorDeviceClass.VOLUME: [{CONF_TYPE: CONF_VOLUME}],
    SensorDeviceClass.VOLUME_STORAGE: [{CONF_TYPE: CONF_VOLUME}],
    SensorDeviceClass.VOLUME_FLOW_RATE: [{CONF_TYPE: CONF_VOLUME_FLOW_RATE}],
    SensorDeviceClass.WATER: [{CONF_TYPE: CONF_WATER}],
    SensorDeviceClass.WEIGHT: [{CONF_TYPE: CONF_WEIGHT}],
    SensorDeviceClass.WIND_DIRECTION: [{CONF_TYPE: CONF_WIND_DIRECTION}],
    SensorDeviceClass.WIND_SPEED: [{CONF_TYPE: CONF_WIND_SPEED}],
    DEVICE_CLASS_NONE: [{CONF_TYPE: CONF_VALUE}],
}


TRIGGER_SCHEMA = vol.All(
    DEVICE_TRIGGER_BASE_SCHEMA.extend(
        {
            vol.Required(CONF_ENTITY_ID): cv.entity_id_or_uuid,
            vol.Required(CONF_TYPE): vol.In(
                [
                    CONF_APPARENT_POWER,
                    CONF_AQI,
                    CONF_AREA,
                    CONF_ATMOSPHERIC_PRESSURE,
                    CONF_BATTERY_LEVEL,
                    CONF_BLOOD_GLUCOSE_CONCENTRATION,
                    CONF_CO,
                    CONF_CO2,
                    CONF_CONDUCTIVITY,
                    CONF_CURRENT,
                    CONF_DATA_RATE,
                    CONF_DATA_SIZE,
                    CONF_DISTANCE,
                    CONF_DURATION,
                    CONF_ENERGY,
                    CONF_ENERGY_DISTANCE,
                    CONF_FREQUENCY,
                    CONF_GAS,
                    CONF_HUMIDITY,
                    CONF_ILLUMINANCE,
                    CONF_IRRADIANCE,
                    CONF_MOISTURE,
                    CONF_MONETARY,
                    CONF_NITROGEN_DIOXIDE,
                    CONF_NITROGEN_MONOXIDE,
                    CONF_NITROUS_OXIDE,
                    CONF_OZONE,
                    CONF_PH,
                    CONF_PM1,
                    CONF_PM10,
                    CONF_PM25,
                    CONF_POWER,
                    CONF_POWER_FACTOR,
                    CONF_PRECIPITATION,
                    CONF_PRECIPITATION_INTENSITY,
                    CONF_PRESSURE,
                    CONF_REACTIVE_POWER,
                    CONF_SIGNAL_STRENGTH,
                    CONF_SOUND_PRESSURE,
                    CONF_SPEED,
                    CONF_SULPHUR_DIOXIDE,
                    CONF_TEMPERATURE,
                    CONF_VOLATILE_ORGANIC_COMPOUNDS,
                    CONF_VOLATILE_ORGANIC_COMPOUNDS_PARTS,
                    CONF_VOLTAGE,
                    CONF_VOLUME,
                    CONF_VOLUME_FLOW_RATE,
                    CONF_WATER,
                    CONF_WEIGHT,
                    CONF_WIND_DIRECTION,
                    CONF_WIND_SPEED,
                    CONF_VALUE,
                ]
            ),
            vol.Optional(CONF_BELOW): vol.Any(vol.Coerce(float)),
            vol.Optional(CONF_ABOVE): vol.Any(vol.Coerce(float)),
            vol.Optional(CONF_FOR): cv.positive_time_period_dict,
        }
    ),
    cv.has_at_least_one_key(CONF_BELOW, CONF_ABOVE),
)


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for state changes based on configuration."""
    numeric_state_config = {
        numeric_state_trigger.CONF_PLATFORM: "numeric_state",
        numeric_state_trigger.CONF_ENTITY_ID: config[CONF_ENTITY_ID],
    }
    if CONF_ABOVE in config:
        numeric_state_config[numeric_state_trigger.CONF_ABOVE] = config[CONF_ABOVE]
    if CONF_BELOW in config:
        numeric_state_config[numeric_state_trigger.CONF_BELOW] = config[CONF_BELOW]
    if CONF_FOR in config:
        numeric_state_config[CONF_FOR] = config[CONF_FOR]

    numeric_state_config = await numeric_state_trigger.async_validate_trigger_config(
        hass, numeric_state_config
    )
    return await numeric_state_trigger.async_attach_trigger(
        hass, numeric_state_config, action, trigger_info, platform_type="device"
    )


async def async_get_triggers(
    hass: HomeAssistant, device_id: str
) -> list[dict[str, str]]:
    """List device triggers."""
    triggers: list[dict[str, str]] = []
    entity_registry = er.async_get(hass)

    entries = [
        entry
        for entry in er.async_entries_for_device(entity_registry, device_id)
        if entry.domain == DOMAIN
    ]

    for entry in entries:
        device_class = get_device_class(hass, entry.entity_id) or DEVICE_CLASS_NONE
        state_class = get_capability(hass, entry.entity_id, ATTR_STATE_CLASS)
        unit_of_measurement = get_unit_of_measurement(hass, entry.entity_id)

        if not unit_of_measurement and not state_class:
            continue

        templates = ENTITY_TRIGGERS.get(
            device_class, ENTITY_TRIGGERS[DEVICE_CLASS_NONE]
        )

        triggers.extend(
            {
                **automation,
                "platform": "device",
                "device_id": device_id,
                "entity_id": entry.id,
                "domain": DOMAIN,
            }
            for automation in templates
        )

    return triggers


async def async_get_trigger_capabilities(
    hass: HomeAssistant, config: ConfigType
) -> dict[str, vol.Schema]:
    """List trigger capabilities."""

    try:
        entry = async_get_entity_registry_entry_or_raise(hass, config[CONF_ENTITY_ID])
        unit_of_measurement = get_unit_of_measurement(hass, entry.entity_id)
    except HomeAssistantError:
        unit_of_measurement = None

    if not unit_of_measurement:
        raise InvalidDeviceAutomationConfig(
            f"No unit of measurement found for trigger entity {config[CONF_ENTITY_ID]}"
        )

    return {
        "extra_fields": vol.Schema(
            {
                vol.Optional(
                    CONF_ABOVE, description={"suffix": unit_of_measurement}
                ): vol.Coerce(float),
                vol.Optional(
                    CONF_BELOW, description={"suffix": unit_of_measurement}
                ): vol.Coerce(float),
                vol.Optional(CONF_FOR): cv.positive_time_period_dict,
            }
        )
    }
