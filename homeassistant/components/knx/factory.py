"""Factory function to initialize KNX devices from config."""
from typing import Optional, Tuple

from xknx import XKNX
from xknx.devices import (
    BinarySensor as XknxBinarySensor,
    Climate as XknxClimate,
    ClimateMode as XknxClimateMode,
    Cover as XknxCover,
    Device as XknxDevice,
    Fan as XknxFan,
    Light as XknxLight,
    Notification as XknxNotification,
    Scene as XknxScene,
    Sensor as XknxSensor,
    Switch as XknxSwitch,
    Weather as XknxWeather,
)

from homeassistant.const import CONF_ADDRESS, CONF_DEVICE_CLASS, CONF_NAME, CONF_TYPE
from homeassistant.helpers.typing import ConfigType

from .const import ColorTempModes, SupportedPlatforms
from .schema import (
    BinarySensorSchema,
    ClimateSchema,
    CoverSchema,
    FanSchema,
    LightSchema,
    SceneSchema,
    SensorSchema,
    SwitchSchema,
    WeatherSchema,
)


def create_knx_device(
    platform: SupportedPlatforms,
    knx_module: XKNX,
    config: ConfigType,
) -> XknxDevice:
    """Return the requested XKNX device."""
    if platform is SupportedPlatforms.light:
        return _create_light(knx_module, config)

    if platform is SupportedPlatforms.cover:
        return _create_cover(knx_module, config)

    if platform is SupportedPlatforms.climate:
        return _create_climate(knx_module, config)

    if platform is SupportedPlatforms.switch:
        return _create_switch(knx_module, config)

    if platform is SupportedPlatforms.sensor:
        return _create_sensor(knx_module, config)

    if platform is SupportedPlatforms.notify:
        return _create_notify(knx_module, config)

    if platform is SupportedPlatforms.scene:
        return _create_scene(knx_module, config)

    if platform is SupportedPlatforms.binary_sensor:
        return _create_binary_sensor(knx_module, config)

    if platform is SupportedPlatforms.weather:
        return _create_weather(knx_module, config)

    if platform is SupportedPlatforms.fan:
        return _create_fan(knx_module, config)


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


def _create_light_color(
    color: str, config: ConfigType
) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
    """Load color configuration from configuration structure."""
    if "individual_colors" in config and color in config["individual_colors"]:
        sub_config = config["individual_colors"][color]
        group_address_switch = sub_config.get(CONF_ADDRESS)
        group_address_switch_state = sub_config.get(LightSchema.CONF_STATE_ADDRESS)
        group_address_brightness = sub_config.get(LightSchema.CONF_BRIGHTNESS_ADDRESS)
        group_address_brightness_state = sub_config.get(
            LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS
        )
        return (
            group_address_switch,
            group_address_switch_state,
            group_address_brightness,
            group_address_brightness_state,
        )
    return None, None, None, None


def _create_light(knx_module: XKNX, config: ConfigType) -> XknxLight:
    """Return a KNX Light device to be used within XKNX."""

    group_address_tunable_white = None
    group_address_tunable_white_state = None
    group_address_color_temp = None
    group_address_color_temp_state = None
    if config[LightSchema.CONF_COLOR_TEMP_MODE] == ColorTempModes.absolute:
        group_address_color_temp = config.get(LightSchema.CONF_COLOR_TEMP_ADDRESS)
        group_address_color_temp_state = config.get(
            LightSchema.CONF_COLOR_TEMP_STATE_ADDRESS
        )
    elif config[LightSchema.CONF_COLOR_TEMP_MODE] == ColorTempModes.relative:
        group_address_tunable_white = config.get(LightSchema.CONF_COLOR_TEMP_ADDRESS)
        group_address_tunable_white_state = config.get(
            LightSchema.CONF_COLOR_TEMP_STATE_ADDRESS
        )

    (
        red_switch,
        red_switch_state,
        red_brightness,
        red_brightness_state,
    ) = _create_light_color(LightSchema.CONF_RED, config)
    (
        green_switch,
        green_switch_state,
        green_brightness,
        green_brightness_state,
    ) = _create_light_color(LightSchema.CONF_GREEN, config)
    (
        blue_switch,
        blue_switch_state,
        blue_brightness,
        blue_brightness_state,
    ) = _create_light_color(LightSchema.CONF_BLUE, config)
    (
        white_switch,
        white_switch_state,
        white_brightness,
        white_brightness_state,
    ) = _create_light_color(LightSchema.CONF_WHITE, config)

    return XknxLight(
        knx_module,
        name=config[CONF_NAME],
        group_address_switch=config.get(CONF_ADDRESS),
        group_address_switch_state=config.get(LightSchema.CONF_STATE_ADDRESS),
        group_address_brightness=config.get(LightSchema.CONF_BRIGHTNESS_ADDRESS),
        group_address_brightness_state=config.get(
            LightSchema.CONF_BRIGHTNESS_STATE_ADDRESS
        ),
        group_address_color=config.get(LightSchema.CONF_COLOR_ADDRESS),
        group_address_color_state=config.get(LightSchema.CONF_COLOR_STATE_ADDRESS),
        group_address_rgbw=config.get(LightSchema.CONF_RGBW_ADDRESS),
        group_address_rgbw_state=config.get(LightSchema.CONF_RGBW_STATE_ADDRESS),
        group_address_tunable_white=group_address_tunable_white,
        group_address_tunable_white_state=group_address_tunable_white_state,
        group_address_color_temperature=group_address_color_temp,
        group_address_color_temperature_state=group_address_color_temp_state,
        group_address_switch_red=red_switch,
        group_address_switch_red_state=red_switch_state,
        group_address_brightness_red=red_brightness,
        group_address_brightness_red_state=red_brightness_state,
        group_address_switch_green=green_switch,
        group_address_switch_green_state=green_switch_state,
        group_address_brightness_green=green_brightness,
        group_address_brightness_green_state=green_brightness_state,
        group_address_switch_blue=blue_switch,
        group_address_switch_blue_state=blue_switch_state,
        group_address_brightness_blue=blue_brightness,
        group_address_brightness_blue_state=blue_brightness_state,
        group_address_switch_white=white_switch,
        group_address_switch_white_state=white_switch_state,
        group_address_brightness_white=white_brightness,
        group_address_brightness_white_state=white_brightness_state,
        min_kelvin=config[LightSchema.CONF_MIN_KELVIN],
        max_kelvin=config[LightSchema.CONF_MAX_KELVIN],
    )


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
        setpoint_shift_mode=config[ClimateSchema.CONF_SETPOINT_SHIFT_MODE],
        setpoint_shift_max=config[ClimateSchema.CONF_SETPOINT_SHIFT_MAX],
        setpoint_shift_min=config[ClimateSchema.CONF_SETPOINT_SHIFT_MIN],
        temperature_step=config[ClimateSchema.CONF_TEMPERATURE_STEP],
        group_address_on_off=config.get(ClimateSchema.CONF_ON_OFF_ADDRESS),
        group_address_on_off_state=config.get(ClimateSchema.CONF_ON_OFF_STATE_ADDRESS),
        min_temp=config.get(ClimateSchema.CONF_MIN_TEMP),
        max_temp=config.get(ClimateSchema.CONF_MAX_TEMP),
        mode=climate_mode,
        on_off_invert=config[ClimateSchema.CONF_ON_OFF_INVERT],
    )


def _create_switch(knx_module: XKNX, config: ConfigType) -> XknxSwitch:
    """Return a KNX switch to be used within XKNX."""
    return XknxSwitch(
        knx_module,
        name=config[CONF_NAME],
        group_address=config[CONF_ADDRESS],
        group_address_state=config.get(SwitchSchema.CONF_STATE_ADDRESS),
        invert=config.get(SwitchSchema.CONF_INVERT),
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


def _create_notify(knx_module: XKNX, config: ConfigType) -> XknxNotification:
    """Return a KNX notification to be used within XKNX."""
    return XknxNotification(
        knx_module,
        name=config[CONF_NAME],
        group_address=config[CONF_ADDRESS],
    )


def _create_scene(knx_module: XKNX, config: ConfigType) -> XknxScene:
    """Return a KNX scene to be used within XKNX."""
    return XknxScene(
        knx_module,
        name=config[CONF_NAME],
        group_address=config[CONF_ADDRESS],
        scene_number=config[SceneSchema.CONF_SCENE_NUMBER],
    )


def _create_binary_sensor(knx_module: XKNX, config: ConfigType) -> XknxBinarySensor:
    """Return a KNX binary sensor to be used within XKNX."""
    device_name = config[CONF_NAME]

    return XknxBinarySensor(
        knx_module,
        name=device_name,
        group_address_state=config[BinarySensorSchema.CONF_STATE_ADDRESS],
        invert=config.get(BinarySensorSchema.CONF_INVERT),
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
        expose_sensors=config[WeatherSchema.CONF_KNX_EXPOSE_SENSORS],
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


def _create_fan(knx_module: XKNX, config: ConfigType) -> XknxFan:
    """Return a KNX Fan device to be used within XKNX."""

    fan = XknxFan(
        knx_module,
        name=config[CONF_NAME],
        group_address_speed=config.get(CONF_ADDRESS),
        group_address_speed_state=config.get(FanSchema.CONF_STATE_ADDRESS),
        group_address_oscillation=config.get(FanSchema.CONF_OSCILLATION_ADDRESS),
        group_address_oscillation_state=config.get(
            FanSchema.CONF_OSCILLATION_STATE_ADDRESS
        ),
        max_step=config.get(FanSchema.CONF_MAX_STEP),
    )
    return fan
