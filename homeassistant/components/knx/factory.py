"""Factory function to initialize KNX devices from config."""
from __future__ import annotations

from xknx import XKNX
from xknx.devices import (
    Climate as XknxClimate,
    ClimateMode as XknxClimateMode,
    Device as XknxDevice,
    Sensor as XknxSensor,
    Weather as XknxWeather,
)

from homeassistant.const import CONF_NAME, CONF_TYPE
from homeassistant.helpers.typing import ConfigType

from .const import SupportedPlatforms
from .schema import ClimateSchema, SensorSchema, WeatherSchema


def create_knx_device(
    platform: SupportedPlatforms,
    knx_module: XKNX,
    config: ConfigType,
) -> XknxDevice | None:
    """Return the requested XKNX device."""
    if platform is SupportedPlatforms.CLIMATE:
        return _create_climate(knx_module, config)

    if platform is SupportedPlatforms.SENSOR:
        return _create_sensor(knx_module, config)

    if platform is SupportedPlatforms.WEATHER:
        return _create_weather(knx_module, config)

    return None


def _create_climate(knx_module: XKNX, config: ConfigType) -> XknxClimate:
    """Return a KNX Climate device to be used within XKNX."""
    climate_mode = XknxClimateMode(
        knx_module,
        name=f"{config[CONF_NAME]} Mode",
        group_address_operation_mode=config.get(
            ClimateSchema.CONF_OPERATION_MODE_ADDRESS
        ),
        group_address_operation_mode_state=config.get(
            ClimateSchema.CONF_OPERATION_MODE_STATE_ADDRESS
        ),
        group_address_controller_status=config.get(
            ClimateSchema.CONF_CONTROLLER_STATUS_ADDRESS
        ),
        group_address_controller_status_state=config.get(
            ClimateSchema.CONF_CONTROLLER_STATUS_STATE_ADDRESS
        ),
        group_address_controller_mode=config.get(
            ClimateSchema.CONF_CONTROLLER_MODE_ADDRESS
        ),
        group_address_controller_mode_state=config.get(
            ClimateSchema.CONF_CONTROLLER_MODE_STATE_ADDRESS
        ),
        group_address_operation_mode_protection=config.get(
            ClimateSchema.CONF_OPERATION_MODE_FROST_PROTECTION_ADDRESS
        ),
        group_address_operation_mode_night=config.get(
            ClimateSchema.CONF_OPERATION_MODE_NIGHT_ADDRESS
        ),
        group_address_operation_mode_comfort=config.get(
            ClimateSchema.CONF_OPERATION_MODE_COMFORT_ADDRESS
        ),
        group_address_operation_mode_standby=config.get(
            ClimateSchema.CONF_OPERATION_MODE_STANDBY_ADDRESS
        ),
        group_address_heat_cool=config.get(ClimateSchema.CONF_HEAT_COOL_ADDRESS),
        group_address_heat_cool_state=config.get(
            ClimateSchema.CONF_HEAT_COOL_STATE_ADDRESS
        ),
        operation_modes=config.get(ClimateSchema.CONF_OPERATION_MODES),
        controller_modes=config.get(ClimateSchema.CONF_CONTROLLER_MODES),
    )

    return XknxClimate(
        knx_module,
        name=config[CONF_NAME],
        group_address_temperature=config[ClimateSchema.CONF_TEMPERATURE_ADDRESS],
        group_address_target_temperature=config.get(
            ClimateSchema.CONF_TARGET_TEMPERATURE_ADDRESS
        ),
        group_address_target_temperature_state=config[
            ClimateSchema.CONF_TARGET_TEMPERATURE_STATE_ADDRESS
        ],
        group_address_setpoint_shift=config.get(
            ClimateSchema.CONF_SETPOINT_SHIFT_ADDRESS
        ),
        group_address_setpoint_shift_state=config.get(
            ClimateSchema.CONF_SETPOINT_SHIFT_STATE_ADDRESS
        ),
        setpoint_shift_mode=config.get(ClimateSchema.CONF_SETPOINT_SHIFT_MODE),
        setpoint_shift_max=config[ClimateSchema.CONF_SETPOINT_SHIFT_MAX],
        setpoint_shift_min=config[ClimateSchema.CONF_SETPOINT_SHIFT_MIN],
        temperature_step=config[ClimateSchema.CONF_TEMPERATURE_STEP],
        group_address_on_off=config.get(ClimateSchema.CONF_ON_OFF_ADDRESS),
        group_address_on_off_state=config.get(ClimateSchema.CONF_ON_OFF_STATE_ADDRESS),
        min_temp=config.get(ClimateSchema.CONF_MIN_TEMP),
        max_temp=config.get(ClimateSchema.CONF_MAX_TEMP),
        mode=climate_mode,
        on_off_invert=config[ClimateSchema.CONF_ON_OFF_INVERT],
        create_temperature_sensors=config[
            ClimateSchema.CONF_CREATE_TEMPERATURE_SENSORS
        ],
    )


def _create_sensor(knx_module: XKNX, config: ConfigType) -> XknxSensor:
    """Return a KNX sensor to be used within XKNX."""
    return XknxSensor(
        knx_module,
        name=config[CONF_NAME],
        group_address_state=config[SensorSchema.CONF_STATE_ADDRESS],
        sync_state=config[SensorSchema.CONF_SYNC_STATE],
        always_callback=config[SensorSchema.CONF_ALWAYS_CALLBACK],
        value_type=config[CONF_TYPE],
    )


def _create_weather(knx_module: XKNX, config: ConfigType) -> XknxWeather:
    """Return a KNX weather device to be used within XKNX."""
    return XknxWeather(
        knx_module,
        name=config[CONF_NAME],
        sync_state=config[WeatherSchema.CONF_SYNC_STATE],
        create_sensors=config[WeatherSchema.CONF_KNX_CREATE_SENSORS],
        group_address_temperature=config[WeatherSchema.CONF_KNX_TEMPERATURE_ADDRESS],
        group_address_brightness_south=config.get(
            WeatherSchema.CONF_KNX_BRIGHTNESS_SOUTH_ADDRESS
        ),
        group_address_brightness_east=config.get(
            WeatherSchema.CONF_KNX_BRIGHTNESS_EAST_ADDRESS
        ),
        group_address_brightness_west=config.get(
            WeatherSchema.CONF_KNX_BRIGHTNESS_WEST_ADDRESS
        ),
        group_address_brightness_north=config.get(
            WeatherSchema.CONF_KNX_BRIGHTNESS_NORTH_ADDRESS
        ),
        group_address_wind_speed=config.get(WeatherSchema.CONF_KNX_WIND_SPEED_ADDRESS),
        group_address_wind_bearing=config.get(
            WeatherSchema.CONF_KNX_WIND_BEARING_ADDRESS
        ),
        group_address_rain_alarm=config.get(WeatherSchema.CONF_KNX_RAIN_ALARM_ADDRESS),
        group_address_frost_alarm=config.get(
            WeatherSchema.CONF_KNX_FROST_ALARM_ADDRESS
        ),
        group_address_wind_alarm=config.get(WeatherSchema.CONF_KNX_WIND_ALARM_ADDRESS),
        group_address_day_night=config.get(WeatherSchema.CONF_KNX_DAY_NIGHT_ADDRESS),
        group_address_air_pressure=config.get(
            WeatherSchema.CONF_KNX_AIR_PRESSURE_ADDRESS
        ),
        group_address_humidity=config.get(WeatherSchema.CONF_KNX_HUMIDITY_ADDRESS),
    )
