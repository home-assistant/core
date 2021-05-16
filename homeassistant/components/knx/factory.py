"""Factory function to initialize KNX devices from config."""
from __future__ import annotations

from xknx import XKNX
from xknx.devices import (
    BinarySensor as XknxBinarySensor,
    Cover as XknxCover,
    Device as XknxDevice,
    Sensor as XknxSensor,
    Weather as XknxWeather,
)

from homeassistant.const import CONF_DEVICE_CLASS, CONF_NAME, CONF_TYPE
from homeassistant.helpers.typing import ConfigType

from .const import SupportedPlatforms
from .schema import BinarySensorSchema, CoverSchema, SensorSchema, WeatherSchema


def create_knx_device(
    platform: SupportedPlatforms,
    knx_module: XKNX,
    config: ConfigType,
) -> XknxDevice | None:
    """Return the requested XKNX device."""
    if platform is SupportedPlatforms.COVER:
        return _create_cover(knx_module, config)

    if platform is SupportedPlatforms.SENSOR:
        return _create_sensor(knx_module, config)

    if platform is SupportedPlatforms.BINARY_SENSOR:
        return _create_binary_sensor(knx_module, config)

    if platform is SupportedPlatforms.WEATHER:
        return _create_weather(knx_module, config)

    return None


def _create_cover(knx_module: XKNX, config: ConfigType) -> XknxCover:
    """Return a KNX Cover device to be used within XKNX."""
    return XknxCover(
        knx_module,
        name=config[CONF_NAME],
        group_address_long=config.get(CoverSchema.CONF_MOVE_LONG_ADDRESS),
        group_address_short=config.get(CoverSchema.CONF_MOVE_SHORT_ADDRESS),
        group_address_stop=config.get(CoverSchema.CONF_STOP_ADDRESS),
        group_address_position_state=config.get(
            CoverSchema.CONF_POSITION_STATE_ADDRESS
        ),
        group_address_angle=config.get(CoverSchema.CONF_ANGLE_ADDRESS),
        group_address_angle_state=config.get(CoverSchema.CONF_ANGLE_STATE_ADDRESS),
        group_address_position=config.get(CoverSchema.CONF_POSITION_ADDRESS),
        travel_time_down=config[CoverSchema.CONF_TRAVELLING_TIME_DOWN],
        travel_time_up=config[CoverSchema.CONF_TRAVELLING_TIME_UP],
        invert_position=config[CoverSchema.CONF_INVERT_POSITION],
        invert_angle=config[CoverSchema.CONF_INVERT_ANGLE],
        device_class=config.get(CONF_DEVICE_CLASS),
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


def _create_binary_sensor(knx_module: XKNX, config: ConfigType) -> XknxBinarySensor:
    """Return a KNX binary sensor to be used within XKNX."""
    device_name = config[CONF_NAME]

    return XknxBinarySensor(
        knx_module,
        name=device_name,
        group_address_state=config[BinarySensorSchema.CONF_STATE_ADDRESS],
        invert=config[BinarySensorSchema.CONF_INVERT],
        sync_state=config[BinarySensorSchema.CONF_SYNC_STATE],
        device_class=config.get(CONF_DEVICE_CLASS),
        ignore_internal_state=config[BinarySensorSchema.CONF_IGNORE_INTERNAL_STATE],
        context_timeout=config.get(BinarySensorSchema.CONF_CONTEXT_TIMEOUT),
        reset_after=config.get(BinarySensorSchema.CONF_RESET_AFTER),
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
