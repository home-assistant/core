"""Make EntityDescription and mapping"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import time
from enum import StrEnum, unique
from typing import Any, Awaitable, Callable, Generic, TypeVar

from homeassistant.components.binary_sensor import (
    BinarySensorEntityDescription,
)
from homeassistant.components.button import ButtonEntityDescription
from homeassistant.components.climate import ClimateEntityDescription
from homeassistant.components.event import EventEntityDescription
from homeassistant.components.fan import FanEntityDescription
from homeassistant.components.humidifier import (
    HumidifierDeviceClass,
    HumidifierEntityDescription,
)
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.components.select import SelectEntityDescription
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.components.switch import SwitchEntityDescription
from homeassistant.components.text import TextEntityDescription
from homeassistant.components.time import TimeEntityDescription
from homeassistant.components.vacuum import StateVacuumEntityDescription
from homeassistant.components.water_heater import (
    WaterHeaterEntityEntityDescription,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    Platform,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import callback
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from thinqconnect.const import DeviceType
from thinqconnect.thinq_api import ThinQApiResponse

from .const import POWER_OFF, POWER_ON, Profile
from .device import LGDevice
from .property import (
    Property,
    PropertyFeature,
    PropertyInfo,
    PropertyMode,
    Range,
    create_properties,
)

_LOGGER = logging.getLogger(__name__)

# Lambda functions for entity operations.
VALIDATE_CREATION_READABLE: Callable[[bool, bool], bool] = (
    lambda readable, writable: readable
)
VALIDATE_CREATION_WRITABLE: Callable[[bool, bool], bool] = (
    lambda readable, writable: writable
)
VALIDATE_CREATION_READONLY: Callable[[bool, bool], bool] = (
    lambda readable, writable: readable and not writable
)
VALUE_TO_INT_CONVERTER: Callable[[Any], int] = lambda value: int(value)
VALUE_TO_STR_CONVERTER: Callable[[Any], str] = lambda value: str(value)
VALUE_TO_POWER_STATE_CONVERTER: Callable[[Any], str] = lambda value: (
    POWER_ON if bool(value) else POWER_OFF
)
VALUE_TO_TIMER_STR_CONVERTER: Callable[[list[Any], str]] = lambda value: (
    f"{value:0>2}" if value is not None and value > 0 else "00"
)
VALUE_TO_TIME_TEXT_CONVERTER: Callable[[Any], AbsoluteTime] = lambda value: (
    AbsoluteTime.str_to_time(value)
    if value
    else AbsoluteTime(hour=-1, minute=-1)
)
# HH:MM:SS
TIMER_COMBINED_SENSOR_FORMATTER: Callable[[list[Any], str]] = (
    lambda values: ":".join(map(VALUE_TO_TIMER_STR_CONVERTER, values))
)
# HH:MM AM,PM
TIMER_COMBINED_2_SENSOR_FORMATTER: Callable[[list[Any], str]] = (
    lambda values: (
        time(values[0], values[1]).strftime("%I:%M %p")
        if values
        and isinstance(values[0], int)
        and values[0] >= 0
        and isinstance(values[1], int)
        and values[1] >= 0
        else None
    )
)
TIMER_COMBINED_TIME_FORMATTER: Callable[[list[Any]], time | None] = (
    lambda values: (
        time(values[0], values[1])
        if values
        and isinstance(values[0], int)
        and values[0] >= 0
        and isinstance(values[1], int)
        and values[1] >= 0
        else None
    )
)
TIMER_COMBINED_TEXT_FORMATTER: Callable[[list[Any], str | None]] = (
    lambda values: (
        f"{values[0]:0>2}:{values[1]:0>2}" if values[0] and values[1] else None
    )
)
TIMER_RELATIVE_HOUR_START_METHOD: Callable[
    [Property, int], Awaitable[ThinQApiResponse]
] = lambda property, value: property.api.set_relative_time_to_start(
    hour=value, minute=0
)
TIMER_RELATIVE_HOUR_STOP_METHOD: Callable[
    [Property, int], Awaitable[ThinQApiResponse]
] = lambda property, value: property.api.set_relative_time_to_stop(
    hour=value, minute=0
)
TIMER_RELATIVE_MINUTE_START_METHOD: Callable[
    [Property, int], Awaitable[ThinQApiResponse]
] = lambda property, value: property.api.set_relative_time_to_start(
    hour=0, minute=value
)
TIMER_RELATIVE_MINUTE_STOP_METHOD: Callable[
    [Property, int], Awaitable[ThinQApiResponse]
] = lambda property, value: property.api.set_relative_time_to_stop(
    hour=0, minute=value
)
TIMER_SLEEP_TIMER_RELATIVE_HOUR_STOP_METHOD: Callable[
    [Property, int], Awaitable[ThinQApiResponse]
] = lambda property, value: property.api.set_sleep_timer_relative_time_to_stop(
    hour=value, minute=0
)
TIMER_SLEEP_TIMER_RELATIVE_MINUTE_STOP_METHOD: Callable[
    [Property, int], Awaitable[ThinQApiResponse]
] = lambda property, value: property.api.set_sleep_timer_relative_time_to_stop(
    hour=0, minute=value
)
TIMER_ABSOLUTE_TIME_START_METHOD: Callable[
    [Property, time], Awaitable[ThinQApiResponse]
] = lambda property, value: property.api.set_absolute_time_to_start(
    hour=value.hour, minute=value.minute
)
TIMER_ABSOLUTE_TIME_STOP_METHOD: Callable[
    [Property, time], Awaitable[ThinQApiResponse]
] = lambda property, value: property.api.set_absolute_time_to_stop(
    hour=value.hour, minute=value.minute
)
TIMER_ABSOLUTE_TEXT_START_METHOD: Callable[
    [Property, AbsoluteTime], Awaitable[ThinQApiResponse]
] = lambda property, value: property.api.set_absolute_time_to_start(
    hour=int(value.hour), minute=int(value.minute)
)
TIMER_ABSOLUTE_TEXT_STOP_METHOD: Callable[
    [Property, AbsoluteTime], Awaitable[ThinQApiResponse]
] = lambda property, value: property.api.set_absolute_time_to_stop(
    hour=int(value.hour), minute=int(value.minute)
)
RANGE_TO_OPTIONS_PROVIDER: Callable[[Profile], list[str]] = (
    lambda profile: Range.range_to_options(profile)
)

# Type hints for lg thinq entity.
ThinQEntityT = TypeVar("ThinQEntityT", bound="ThinQEntity")
ThinQEntityDescriptionT = TypeVar(
    "ThinQEntityDescriptionT", bound="ThinQEntityDescription"
)


@dataclass(kw_only=True)
class AbsoluteTime:
    """For absolute instead of time has min limit"""

    hour: int
    minute: int

    @classmethod
    def str_to_time(cls, time_string: str):
        h, f, m = time_string.partition(":")
        if h and m:
            return cls(hour=h, minute=m)
        else:
            return None


@dataclass(kw_only=True)
class ThinQEntityDescription(EntityDescription):
    """The base thinq entity description."""

    has_entity_name = True
    property_info: PropertyInfo = None

    def __post_init__(self) -> None:
        """Post initialize."""
        # If a property info is not exist, create default one.
        if self.property_info is None:
            self.property_info = PropertyInfo(key=self.key)


@dataclass(kw_only=True)
class ThinQBinarySensorEntityDescription(
    ThinQEntityDescription, BinarySensorEntityDescription
):
    """The entity description for binary sensor."""


@dataclass(kw_only=True)
class ThinQButtonEntityDescription(
    ThinQEntityDescription, ButtonEntityDescription
):
    """The entity description for button."""

    arg: Any = None


@dataclass(kw_only=True)
class ThinQClimateEntityDescription(
    ThinQEntityDescription, ClimateEntityDescription
):
    """The entity description for climate."""


@dataclass(kw_only=True)
class ThinQEventEntityDescription(
    ThinQEntityDescription, EventEntityDescription
):
    """The entity description for event."""


@dataclass(kw_only=True)
class ThinQFanEntityDescription(ThinQEntityDescription, FanEntityDescription):
    """The entity description for fan."""


@dataclass(kw_only=True)
class ThinQHumidifierEntityDescription(
    ThinQEntityDescription, HumidifierEntityDescription
):
    """The entity description for humidifier."""


@dataclass(kw_only=True)
class ThinQNumberEntityDescription(
    ThinQEntityDescription, NumberEntityDescription
):
    """The entity description for number."""


@dataclass(kw_only=True)
class ThinQSelectEntityDescription(
    ThinQEntityDescription, SelectEntityDescription
):
    """The entity description for select."""


@dataclass(kw_only=True)
class ThinQSensorEntityDescription(
    ThinQEntityDescription, SensorEntityDescription
):
    """The entity description for sensor."""


@dataclass(kw_only=True)
class ThinQStateVacuumEntityDescription(
    ThinQEntityDescription, StateVacuumEntityDescription
):
    """The entity description for vacuum."""


@dataclass(kw_only=True)
class ThinQSwitchEntityDescription(
    ThinQEntityDescription, SwitchEntityDescription
):
    """The entity description for switch."""


@dataclass(kw_only=True)
class ThinQTextEntityDescription(
    ThinQEntityDescription, TextEntityDescription
):
    """The entity description for text."""


@dataclass(kw_only=True)
class ThinQTimeEntityDescription(
    ThinQEntityDescription, TimeEntityDescription
):
    """The entity description for datetime."""


@dataclass(kw_only=True)
class ThinQWaterHeaterEntityEntityDescription(
    ThinQEntityDescription, WaterHeaterEntityEntityDescription
):
    """The entity description for water heater."""


@unique
class Common(StrEnum):
    """Properties in common module."""

    ERROR = "error"
    NOTIFICATION = "notification"


COMMON_SENSOR_DESC: dict[Common, ThinQSensorEntityDescription] = {
    Common.ERROR: ThinQSensorEntityDescription(
        key=Common.ERROR,
        icon="mdi:alert-circle-outline",
        name="Error",
        translation_key=Common.ERROR,
    ),
    Common.NOTIFICATION: ThinQSensorEntityDescription(
        key=Common.NOTIFICATION,
        icon="mdi:message-badge-outline",
        name="Noti.",
        translation_key=Common.NOTIFICATION,
        property_info=PropertyInfo(
            key=Common.NOTIFICATION,
            self_validation=True,
            alt_get_method=lambda property: property.device.noti_message,
        ),
    ),
}
NOTIFICATION_EVENT: tuple[ThinQEventEntityDescription, ...] = (
    ThinQEventEntityDescription(
        key=Common.NOTIFICATION,
        icon="mdi:message-badge-outline",
        name=None,
        translation_key=Common.NOTIFICATION,
        property_info=PropertyInfo(
            key=Common.NOTIFICATION,
            alt_get_method=lambda property: property.device.noti_message,
        ),
    ),
)


@unique
class AirFlow(StrEnum):
    """Properties in 'airFlow' module."""

    WIND_STRENGTH = "wind_strength"
    WIND_STEP = "wind_step"
    WIND_TEMPERATURE = "wind_temperature"
    WIND_ANGLE = "wind_angle"
    WARM_MODE = "warm_mode"


AIR_FLOW_NUMBER_DESC: dict[AirFlow, ThinQNumberEntityDescription] = {
    AirFlow.WIND_TEMPERATURE: ThinQNumberEntityDescription(
        key=AirFlow.WIND_TEMPERATURE,
        icon="mdi:thermometer",
        name="Wind Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key=AirFlow.WIND_TEMPERATURE,
    )
}
AIR_FLOW_SELECT_DESC: dict[AirFlow, ThinQSelectEntityDescription] = {
    AirFlow.WIND_STRENGTH: ThinQSelectEntityDescription(
        key=AirFlow.WIND_STRENGTH,
        icon="mdi:wind-power-outline",
        name="Speed",
        translation_key=AirFlow.WIND_STRENGTH,
    ),
    AirFlow.WIND_ANGLE: ThinQSelectEntityDescription(
        key=AirFlow.WIND_ANGLE,
        icon="mdi:rotate-360",
        name="Rotation",
        translation_key=AirFlow.WIND_ANGLE,
    ),
    AirFlow.WARM_MODE: ThinQSelectEntityDescription(
        key=AirFlow.WARM_MODE,
        icon="mdi:heat-wave",
        name="Heating",
        translation_key=AirFlow.WARM_MODE,
    ),
}


@unique
class AirQuality(StrEnum):
    """Properties in 'airQualitySensor' module."""

    PM1 = "pm1"
    PM2 = "pm2"
    PM10 = "pm10"
    ODER = "oder"
    ODOR = "odor"
    HUMIDITY = "humidity"
    TOTAL_POLLUTION = "total_pollution"
    MONITORING_ENABLED = "monitoring_enabled"
    TEMPERATURE = "temperature"


AIR_QUALITY_SENSOR_DESC: dict[AirQuality, ThinQSensorEntityDescription] = {
    AirQuality.PM1: ThinQSensorEntityDescription(
        key=AirQuality.PM1,
        device_class=SensorDeviceClass.PM1,
        name="PM1.0",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=AirQuality.PM1,
    ),
    AirQuality.PM2: ThinQSensorEntityDescription(
        key=AirQuality.PM2,
        device_class=SensorDeviceClass.PM25,
        name="PM2.5",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=AirQuality.PM2,
    ),
    AirQuality.PM10: ThinQSensorEntityDescription(
        key=AirQuality.PM10,
        device_class=SensorDeviceClass.PM10,
        name="PM10",
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=AirQuality.PM10,
    ),
    AirQuality.HUMIDITY: ThinQSensorEntityDescription(
        key=AirQuality.HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        name="Humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=AirQuality.HUMIDITY,
    ),
    AirQuality.ODOR: ThinQSensorEntityDescription(
        key=AirQuality.ODOR,
        icon="mdi:scent",
        name="Odor",
        translation_key=AirQuality.ODOR,
    ),
    AirQuality.ODER: ThinQSensorEntityDescription(
        key=AirQuality.ODER,
        icon="mdi:scent",
        name="Odor",
        translation_key=AirQuality.ODOR,
    ),
    AirQuality.TOTAL_POLLUTION: ThinQSensorEntityDescription(
        key=AirQuality.TOTAL_POLLUTION,
        icon="mdi:air-filter",
        name="Overall Air Quality",
        translation_key=AirQuality.TOTAL_POLLUTION,
    ),
    AirQuality.MONITORING_ENABLED: ThinQSensorEntityDescription(
        key=AirQuality.MONITORING_ENABLED,
        icon="mdi:monitor-eye",
        name="Air Quality Sensor",
        translation_key=AirQuality.MONITORING_ENABLED,
    ),
    AirQuality.TEMPERATURE: ThinQSensorEntityDescription(
        key=AirQuality.TEMPERATURE,
        icon="mdi:thermometer",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=AirQuality.TEMPERATURE,
    ),
}
AIR_QUALITY_SELECT_DESC: dict[AirQuality, ThinQSelectEntityDescription] = {
    AirQuality.MONITORING_ENABLED: ThinQSelectEntityDescription(
        key=AirQuality.MONITORING_ENABLED,
        icon="mdi:monitor-eye",
        name="Air Quality Sensor",
        translation_key=AirQuality.MONITORING_ENABLED,
    ),
}


@unique
class Battery(StrEnum):
    """Properties in 'battery' module."""

    LEVEL = "battery_level"
    PERCENT = "battery_percent"


BATTERY_SENSOR_DESC: dict[Battery, ThinQSensorEntityDescription] = {
    Battery.LEVEL: ThinQSensorEntityDescription(
        key=Battery.LEVEL,
        icon="mdi:battery-outline",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        translation_key=Battery.LEVEL,
        property_info=PropertyInfo(
            key=Battery.LEVEL,
            mode=PropertyMode.SELECTIVE,
            children=(PropertyInfo(key=Battery.PERCENT),),
        ),
    ),
}


@unique
class Cook(StrEnum):
    """Properties in 'cook' module."""

    COOK_MODE = "cook_mode"


COOK_SELECT_DESC: dict[Cook, ThinQSelectEntityDescription] = {
    Cook.COOK_MODE: ThinQSelectEntityDescription(
        key=Cook.COOK_MODE,
        icon="mdi:chef-hat",
        name="Cook Mode",
        translation_key=Cook.COOK_MODE,
    ),
}


@unique
class Course(StrEnum):
    """Properties in 'course' module."""

    STYLING_COURSE = "styling_course"


COURSE_SELECT_DESC: dict[Course, ThinQSelectEntityDescription] = {
    Course.STYLING_COURSE: ThinQSelectEntityDescription(
        key=Course.STYLING_COURSE,
        icon="mdi:tshirt-crew",
        name="Styling",
        translation_key=Course.STYLING_COURSE,
    ),
}


@unique
class Detergent(StrEnum):
    """Properties in 'detergent' module."""

    DETERGENT_SETTING = "detergent_setting"


DETERGENT_SENSOR_DESC: dict[Detergent, ThinQSensorEntityDescription] = {
    Detergent.DETERGENT_SETTING: ThinQSensorEntityDescription(
        key=Detergent.DETERGENT_SETTING,
        icon="mdi:tune-vertical-variant",
        name="Default Detergent",
        translation_key=Detergent.DETERGENT_SETTING,
    ),
}


@unique
class DishWashingCourse(StrEnum):
    """Properties in 'dishWashingCourse' module."""

    CURRENT_DISH_WASHING_COURSE = "current_dish_washing_course"


DISH_WASHING_COURSE_SENSOR_DESC: dict[
    DishWashingCourse, ThinQSensorEntityDescription
] = {
    DishWashingCourse.CURRENT_DISH_WASHING_COURSE: ThinQSensorEntityDescription(
        key=DishWashingCourse.CURRENT_DISH_WASHING_COURSE,
        icon="mdi:format-list-checks",
        name="Current Cycle",
        translation_key=DishWashingCourse.CURRENT_DISH_WASHING_COURSE,
    )
}


@unique
class DishWashingStatus(StrEnum):
    """Properties in 'dishWashingStatus' module."""

    RINSE_REFILL = "rinse_refill"


DISH_WASHING_STATUS_BINARY_SENSOR_DESC: dict[
    DishWashingStatus, ThinQBinarySensorEntityDescription
] = {
    DishWashingStatus.RINSE_REFILL: ThinQBinarySensorEntityDescription(
        key=DishWashingStatus.RINSE_REFILL,
        icon="mdi:tune-vertical-variant",
        name="Rinse refill needed",
        translation_key=DishWashingStatus.RINSE_REFILL,
    ),
}


@unique
class Display(StrEnum):
    """Properties in 'display' module."""

    LIGHT = "display_light"


DISPLAY_SELECT_DESC: dict[Display, ThinQSelectEntityDescription] = {
    Display.LIGHT: ThinQSelectEntityDescription(
        key=Display.LIGHT,
        icon="mdi:brightness-6",
        name="Display Brightness",
        translation_key=Display.LIGHT,
    )
}


@unique
class DoorStatus(StrEnum):
    """Properties in 'doorStatus' module."""

    DOOR_STATE = "door_state"


DOOR_STATUS_SENSOR_DESC: dict[DoorStatus, ThinQSensorEntityDescription] = {
    DoorStatus.DOOR_STATE: ThinQSensorEntityDescription(
        key=DoorStatus.DOOR_STATE,
        icon="mdi:door",
        name="Door",
        translation_key=DoorStatus.DOOR_STATE,
    ),
}


@unique
class EcoFriendly(StrEnum):
    """Properties in 'ecoFriendly' module."""

    ECO_FRIENDLY_MODE = "eco_friendly_mode"


ECO_FRIENDLY_BINARY_SENSOR_DESC: dict[
    EcoFriendly, ThinQBinarySensorEntityDescription
] = {
    EcoFriendly.ECO_FRIENDLY_MODE: ThinQBinarySensorEntityDescription(
        key=EcoFriendly.ECO_FRIENDLY_MODE,
        icon="mdi:sprout",
        name="Eco Friendly",
        translation_key=EcoFriendly.ECO_FRIENDLY_MODE,
    ),
}


@unique
class FilterInfo(StrEnum):
    """Properties in 'filterInfo' module."""

    USED_TIME = "used_time"
    FILTER_LIFE_TIME = "filter_lifetime"


FILTER_INFO_SENSOR_DESC: dict[
    WaterFilterInfo, ThinQSensorEntityDescription
] = {
    FilterInfo.FILTER_LIFE_TIME: ThinQSensorEntityDescription(
        key=FilterInfo.FILTER_LIFE_TIME,
        icon="mdi:air-filter",
        name="Filter Remaining",
        native_unit_of_measurement=UnitOfTime.HOURS,
        translation_key=FilterInfo.FILTER_LIFE_TIME,
    ),
}


@unique
class Humidity(StrEnum):
    """Properties in 'humidity' module."""

    CURRENT_HUMIDITY = "current_humidity"
    TARGET_HUMIDITY = "target_humidity"
    WARM_MODE = "warm_mode"


HUMIDITY_NUMBER_DESC: dict[Humidity, ThinQNumberEntityDescription] = {
    Humidity.TARGET_HUMIDITY: ThinQNumberEntityDescription(
        key=Humidity.TARGET_HUMIDITY,
        device_class=NumberDeviceClass.HUMIDITY,
        mode=NumberMode.SLIDER,
        name="Target Humidity",
        native_unit_of_measurement=PERCENTAGE,
        translation_key=Humidity.TARGET_HUMIDITY,
    )
}
HUMIDITY_SELECT_DESC: dict[Humidity, ThinQSelectEntityDescription] = {
    Humidity.WARM_MODE: ThinQSelectEntityDescription(
        key=Humidity.WARM_MODE,
        icon="mdi:heat-wave",
        name="Warm Mist",
        translation_key="humidity_warm_mode",
    )
}
HUMIDITY_SENSOR_DESC: dict[Humidity, ThinQSensorEntityDescription] = {
    Humidity.CURRENT_HUMIDITY: ThinQSensorEntityDescription(
        key=Humidity.CURRENT_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        name="Current Humidity",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=Humidity.CURRENT_HUMIDITY,
    )
}


@unique
class JobMode(StrEnum):
    """Properties in '{type}jobMode' module."""

    CURRENT_JOB_MODE = "current_job_mode"
    PERSONALIZATION_MODE = "personalization_mode"


JOB_MODE_SELECT_DESC: dict[JobMode, ThinQSelectEntityDescription] = {
    JobMode.CURRENT_JOB_MODE: ThinQSelectEntityDescription(
        key=JobMode.CURRENT_JOB_MODE,
        icon="mdi:dots-circle",
        name="Operating Mode",
        translation_key=JobMode.CURRENT_JOB_MODE,
    )
}
JOB_MODE_SENSOR_DESC: dict[JobMode, ThinQSensorEntityDescription] = {
    JobMode.CURRENT_JOB_MODE: ThinQSensorEntityDescription(
        key=JobMode.CURRENT_JOB_MODE,
        icon="mdi:dots-circle",
        name="Operating Mode",
        translation_key=JobMode.CURRENT_JOB_MODE,
    ),
    JobMode.PERSONALIZATION_MODE: ThinQSensorEntityDescription(
        key=JobMode.PERSONALIZATION_MODE,
        icon="mdi:dots-circle",
        name="Personal Mode",
        translation_key=JobMode.PERSONALIZATION_MODE,
    ),
}


@unique
class Lamp(StrEnum):
    """Properties in 'lamp' module."""

    LAMP_BRIGHTNESS = "lamp_brightness"


LAMP_NUMBER_DESC: dict[Lamp, ThinQNumberEntityDescription] = {
    Lamp.LAMP_BRIGHTNESS: ThinQNumberEntityDescription(
        key=Lamp.LAMP_BRIGHTNESS,
        icon="mdi:alarm-light-outline",
        name="Light",
        translation_key=Lamp.LAMP_BRIGHTNESS,
    ),
}


@unique
class Light(StrEnum):
    """Properties in 'light' module."""

    BRIGHTNESS = "brightness"
    DURATION = "duration"
    START_TIME = "start"
    START_HOUR = "start_hour"
    START_MINUTE = "start_minute"
    END_TIME = "end"
    END_HOUR = "end_hour"
    END_MINUTE = "end_minute"


LIGHT_SENSOR_DESC: dict[Lamp, ThinQSensorEntityDescription] = {
    Light.BRIGHTNESS: ThinQSensorEntityDescription(
        key=Light.BRIGHTNESS,
        icon="mdi:tune-vertical-variant",
        name="Lighting Intensity",
        translation_key=Light.BRIGHTNESS,
    ),
    Light.DURATION: ThinQSensorEntityDescription(
        key=Light.DURATION,
        icon="mdi:tune-vertical-variant",
        name="Lighting Duration",
        native_unit_of_measurement=UnitOfTime.HOURS,
        translation_key=Light.DURATION,
    ),
    Light.START_TIME: ThinQSensorEntityDescription(
        key=Light.START_TIME,
        icon="mdi:clock-time-three-outline",
        name="Lighting On Time",
        translation_key="light_start",
        property_info=PropertyInfo(
            key=Light.START_TIME,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(key=Light.START_HOUR),
                PropertyInfo(key=Light.START_MINUTE),
            ),
            value_formatter=TIMER_COMBINED_2_SENSOR_FORMATTER,
        ),
    ),
    Light.END_TIME: ThinQSensorEntityDescription(
        key=Light.END_TIME,
        icon="mdi:clock-time-three-outline",
        name="Lighting Off Time",
        translation_key="light_end",
        property_info=PropertyInfo(
            key=Light.END_TIME,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(key=Light.END_HOUR),
                PropertyInfo(key=Light.END_MINUTE),
            ),
            value_formatter=TIMER_COMBINED_2_SENSOR_FORMATTER,
        ),
    ),
}


@unique
class Misc(StrEnum):
    """Properties in 'misc' module."""

    UV_NANO = "uv_nano"


MISC_SELECT_DESC: dict[Misc, ThinQSelectEntityDescription] = {
    Misc.UV_NANO: ThinQSelectEntityDescription(
        key=Misc.UV_NANO,
        icon="mdi:air-filter",
        name="UVnano",
        translation_key=Misc.UV_NANO,
    )
}


@unique
class MoodLamp(StrEnum):
    """Properties in 'moodLamp' module."""

    MOOD_LAMP_STATE = "mood_lamp_state"


MOOD_LAMP_SELECT_DESC: dict[MoodLamp, ThinQSelectEntityDescription] = {
    MoodLamp.MOOD_LAMP_STATE: ThinQSelectEntityDescription(
        key=MoodLamp.MOOD_LAMP_STATE,
        icon="mdi:lamp",
        name="Mood light",
        translation_key=MoodLamp.MOOD_LAMP_STATE,
    ),
}


@unique
class Operation(StrEnum):
    """Properties in 'operation' module."""

    AIR_CLEAN_OPERATION_MODE = "air_clean_operation_mode"
    AIR_CON_OPERATION_MODE = "air_con_operation_mode"
    AIR_FAN_OPERATION_MODE = "air_fan_operation_mode"
    AIR_PURIFIER_OPERATION_MODE = "air_purifier_operation_mode"
    AUTO_MODE = "auto_mode"
    BOILER_OPERATION_MODE = "boiler_operation_mode"
    CEILING_FAN_OPERATION_MODE = "ceiling_fan_operation_mode"
    CLEAN_OPERATION_MODE = "clean_operation_mode"
    DEHUMIDIFIER_OPERATION_MODE = "dehumidifier_operation_mode"
    DISH_WASHER_OPERATION_MODE = "dish_washer_operation_mode"
    DRYER_OPERATION_MODE = "dryer_operation_mode"
    HOOD_OPERATION_MODE = "hood_operation_mode"
    HOT_WATER_MODE = "hot_water_mode"
    HUMIDIFIER_OPERATION_MODE = "humidifier_operation_mode"
    HYGIENE_DRY_MODE = "hygiene_dry_mode"
    LIGHT_BRIGHTNESS = "light_brightness"
    LIGHT_STATUS = "light_status"
    OPERATION_MODE = "operation_mode"
    OPTIMAL_HUMIDITY = "optimal_humidity"
    OVEN_OPERATION_MODE = "oven_operation_mode"
    SLEEP_MODE = "sleep_mode"
    STYLER_OPERATION_MODE = "styler_operation_mode"
    WATER_HEATER_OPERATION_MODE = "water_heater_operation_mode"
    WASHER_OPERATION_MODE = "washer_operation_mode"


OPERATION_BUTTON_DESC: dict[Operation, ThinQButtonEntityDescription] = {
    Operation.OPERATION_MODE: ThinQButtonEntityDescription(
        key=Operation.OPERATION_MODE,
        icon="mdi:power",
        name="Power Off",
        translation_key="power_off",
        arg="POWER_OFF",
    )
}
OPERATION_NUMBER_DESC: dict[Operation, ThinQNumberEntityDescription] = {
    Operation.LIGHT_STATUS: ThinQNumberEntityDescription(
        key=Operation.LIGHT_STATUS,
        icon="mdi:television-ambient-light",
        name="Light",
        native_unit_of_measurement=PERCENTAGE,
        translation_key=Operation.LIGHT_STATUS,
    )
}
OPERATION_SELECT_DESC: dict[Operation, ThinQSelectEntityDescription] = {
    Operation.AIR_CLEAN_OPERATION_MODE: ThinQSelectEntityDescription(
        key=Operation.AIR_CLEAN_OPERATION_MODE,
        icon="mdi:air-filter",
        name="Air Purify",
        translation_key=Operation.AIR_CLEAN_OPERATION_MODE,
    ),
    Operation.AUTO_MODE: ThinQSelectEntityDescription(
        key=Operation.AUTO_MODE,
        icon="mdi:cogs",
        name="Auto Mode",
        translation_key=Operation.AUTO_MODE,
    ),
    Operation.DISH_WASHER_OPERATION_MODE: ThinQSelectEntityDescription(
        key=Operation.DISH_WASHER_OPERATION_MODE,
        icon="mdi:dishwasher",
        name="Washer operation",
        translation_key=Operation.OPERATION_MODE,
    ),
    Operation.DRYER_OPERATION_MODE: ThinQSelectEntityDescription(
        key=Operation.DRYER_OPERATION_MODE,
        icon="mdi:gesture-tap-button",
        name="Dryer operation",
        translation_key=Operation.OPERATION_MODE,
    ),
    Operation.HOT_WATER_MODE: ThinQSelectEntityDescription(
        key=Operation.HOT_WATER_MODE,
        icon="mdi:list-status",
        name="Hot Water",
        translation_key=Operation.HOT_WATER_MODE,
    ),
    Operation.HYGIENE_DRY_MODE: ThinQSelectEntityDescription(
        key=Operation.HYGIENE_DRY_MODE,
        icon="mdi:cogs",
        name="Drying Mode",
        translation_key=Operation.HYGIENE_DRY_MODE,
    ),
    Operation.LIGHT_BRIGHTNESS: ThinQSelectEntityDescription(
        key=Operation.LIGHT_BRIGHTNESS,
        icon="mdi:list-status",
        name="Light",
        translation_key=Operation.LIGHT_BRIGHTNESS,
    ),
    Operation.OPTIMAL_HUMIDITY: ThinQSelectEntityDescription(
        key=Operation.OPTIMAL_HUMIDITY,
        icon="mdi:water-percent",
        name="Ventilation",
        translation_key=Operation.OPTIMAL_HUMIDITY,
    ),
    Operation.OVEN_OPERATION_MODE: ThinQSelectEntityDescription(
        key=Operation.OVEN_OPERATION_MODE,
        icon="mdi:list-status",
        name="Operation Mode",
        translation_key=Operation.OPERATION_MODE,
    ),
    Operation.SLEEP_MODE: ThinQSelectEntityDescription(
        key=Operation.SLEEP_MODE,
        icon="mdi:cogs",
        name="Sleep Mode",
        translation_key=Operation.SLEEP_MODE,
    ),
    Operation.STYLER_OPERATION_MODE: ThinQSelectEntityDescription(
        key=Operation.STYLER_OPERATION_MODE,
        icon="mdi:tumble-dryer-alert",
        name="Styler operation",
        translation_key=Operation.OPERATION_MODE,
    ),
    Operation.WASHER_OPERATION_MODE: ThinQSelectEntityDescription(
        key=Operation.WASHER_OPERATION_MODE,
        icon="mdi:gesture-tap-button",
        name="Washer operation",
        translation_key=Operation.OPERATION_MODE,
    ),
}
OPERATION_SENSOR_DESC: dict[Operation, ThinQSensorEntityDescription] = {
    Operation.HOOD_OPERATION_MODE: ThinQSensorEntityDescription(
        key=Operation.HOOD_OPERATION_MODE,
        icon="mdi:power",
        name="Operation mode",
        translation_key=Operation.OPERATION_MODE,
    ),
    Operation.WATER_HEATER_OPERATION_MODE: ThinQSensorEntityDescription(
        key=Operation.WATER_HEATER_OPERATION_MODE,
        icon="mdi:power",
        name="Operation mode",
        translation_key=Operation.OPERATION_MODE,
    ),
}
OPERATION_SWITCH_DESC: dict[Operation, ThinQSwitchEntityDescription] = {
    Operation.AIR_FAN_OPERATION_MODE: ThinQSwitchEntityDescription(
        key=Operation.AIR_FAN_OPERATION_MODE,
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=Operation.AIR_FAN_OPERATION_MODE,
            value_converter=VALUE_TO_POWER_STATE_CONVERTER,
        ),
    ),
    Operation.AIR_PURIFIER_OPERATION_MODE: ThinQSwitchEntityDescription(
        key=Operation.AIR_PURIFIER_OPERATION_MODE,
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=Operation.AIR_PURIFIER_OPERATION_MODE,
            value_converter=VALUE_TO_POWER_STATE_CONVERTER,
        ),
    ),
    Operation.BOILER_OPERATION_MODE: ThinQSwitchEntityDescription(
        key=Operation.BOILER_OPERATION_MODE,
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=Operation.BOILER_OPERATION_MODE,
            value_converter=VALUE_TO_POWER_STATE_CONVERTER,
        ),
    ),
    Operation.DEHUMIDIFIER_OPERATION_MODE: ThinQSwitchEntityDescription(
        key=Operation.DEHUMIDIFIER_OPERATION_MODE,
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=Operation.DEHUMIDIFIER_OPERATION_MODE,
            value_converter=VALUE_TO_POWER_STATE_CONVERTER,
        ),
    ),
    Operation.HUMIDIFIER_OPERATION_MODE: ThinQSwitchEntityDescription(
        key=Operation.HUMIDIFIER_OPERATION_MODE,
        icon="mdi:power",
        name="Power",
        translation_key="operation_power",
        property_info=PropertyInfo(
            key=Operation.HUMIDIFIER_OPERATION_MODE,
            value_converter=VALUE_TO_POWER_STATE_CONVERTER,
        ),
    ),
}


@unique
class Power(StrEnum):
    """Properties in 'power' module."""

    POWER_LEVEL = "power_level"


POWER_NUMBER_DESC: dict[Power, ThinQNumberEntityDescription] = {
    Power.POWER_LEVEL: ThinQNumberEntityDescription(
        key=Power.POWER_LEVEL,
        icon="mdi:radiator",
        name="Power level",
        translation_key=Power.POWER_LEVEL,
    )
}
POWER_SENSOR_DESC: dict[Power, ThinQSensorEntityDescription] = {
    Power.POWER_LEVEL: ThinQSensorEntityDescription(
        key=Power.POWER_LEVEL,
        icon="mdi:radiator",
        name="Power level",
        translation_key=Power.POWER_LEVEL,
        property_info=PropertyInfo(
            key=Power.POWER_LEVEL,
            alt_validate_creation=VALIDATE_CREATION_READABLE,
        ),
    )
}


@unique
class PowerSave(StrEnum):
    """Properties in 'powerSave' module."""

    POWER_SAVE_ENABLED = "power_save_enabled"


POWER_SAVE_BINARY_SENSOR_DESC: dict[
    PowerSave, ThinQBinarySensorEntityDescription
] = {
    PowerSave.POWER_SAVE_ENABLED: ThinQBinarySensorEntityDescription(
        key=PowerSave.POWER_SAVE_ENABLED,
        icon="mdi:meter-electric",
        name="Power Saving Mode",
        translation_key=PowerSave.POWER_SAVE_ENABLED,
    ),
}
POWER_SAVE_SELECT_DESC: dict[PowerSave, ThinQSelectEntityDescription] = {
    PowerSave.POWER_SAVE_ENABLED: ThinQSelectEntityDescription(
        key=PowerSave.POWER_SAVE_ENABLED,
        icon="mdi:hydro-power",
        name="Power Saving Mode",
        translation_key=PowerSave.POWER_SAVE_ENABLED,
    ),
}


@unique
class Preference(StrEnum):
    """Properties in 'preference' module."""

    RINSE_LEVEL = "rinse_level"
    SOFTENING_LEVEL = "softening_level"
    M_C_REMINDER = "machine_clean_reminder"
    SIGNAL_LEVEL = "signal_level"
    CLEAN_L_REMINDER = "clean_light_reminder"


PREFERENCE_SENSOR_DESC: dict[Preference, ThinQSensorEntityDescription] = {
    Preference.RINSE_LEVEL: ThinQSensorEntityDescription(
        key=Preference.RINSE_LEVEL,
        icon="mdi:tune-vertical-variant",
        name="Rinse Aid Dispenser Level",
        translation_key=Preference.RINSE_LEVEL,
    ),
    Preference.SOFTENING_LEVEL: ThinQSensorEntityDescription(
        key=Preference.SOFTENING_LEVEL,
        icon="mdi:tune-vertical-variant",
        name="Softening Level",
        translation_key=Preference.SOFTENING_LEVEL,
    ),
    Preference.M_C_REMINDER: ThinQSensorEntityDescription(
        key=Preference.M_C_REMINDER,
        icon="mdi:tune-vertical-variant",
        name="Machine Clean Reminder",
        translation_key=Preference.M_C_REMINDER,
    ),
    Preference.SIGNAL_LEVEL: ThinQSensorEntityDescription(
        key=Preference.SIGNAL_LEVEL,
        icon="mdi:tune-vertical-variant",
        name="Chime Sound",
        translation_key=Preference.SIGNAL_LEVEL,
    ),
    Preference.CLEAN_L_REMINDER: ThinQSensorEntityDescription(
        key=Preference.CLEAN_L_REMINDER,
        icon="mdi:tune-vertical-variant",
        name="Clean Indicator Light",
        translation_key=Preference.CLEAN_L_REMINDER,
    ),
}


@unique
class Recipe(StrEnum):
    """Properties in 'recipe' module."""

    RECIPE_NAME = "recipe_name"
    WORT_INFO = "wort_info"
    YEAST_INFO = "yeast_info"
    HOP_OIL_INFO = "hop_oil_info"
    FLAVOR_INFO = "flavor_info"
    BEER_REMAIN = "beer_remain"


RECIPE_SENSOR_DESC: dict[Recipe, ThinQSensorEntityDescription] = {
    Recipe.RECIPE_NAME: ThinQSensorEntityDescription(
        key=Recipe.RECIPE_NAME,
        icon="mdi:information-box-outline",
        name="Homebrew Recipe",
        translation_key=Recipe.RECIPE_NAME,
    ),
    Recipe.WORT_INFO: ThinQSensorEntityDescription(
        key=Recipe.WORT_INFO,
        icon="mdi:information-box-outline",
        name="Wort",
        translation_key=Recipe.WORT_INFO,
    ),
    Recipe.YEAST_INFO: ThinQSensorEntityDescription(
        key=Recipe.YEAST_INFO,
        icon="mdi:information-box-outline",
        name="Yeast",
        translation_key=Recipe.YEAST_INFO,
    ),
    Recipe.HOP_OIL_INFO: ThinQSensorEntityDescription(
        key=Recipe.HOP_OIL_INFO,
        icon="mdi:information-box-outline",
        name="Hops",
        translation_key=Recipe.HOP_OIL_INFO,
    ),
    Recipe.FLAVOR_INFO: ThinQSensorEntityDescription(
        key=Recipe.FLAVOR_INFO,
        icon="mdi:information-box-outline",
        name="Flavor",
        translation_key=Recipe.FLAVOR_INFO,
    ),
    Recipe.BEER_REMAIN: ThinQSensorEntityDescription(
        key=Recipe.BEER_REMAIN,
        icon="mdi:glass-mug-variant",
        name="Recipe Progress",
        native_unit_of_measurement=PERCENTAGE,
        translation_key=Recipe.BEER_REMAIN,
    ),
}


@unique
class Refrigeration(StrEnum):
    """Properties in 'refrigeration' module."""

    EXPRESS_MODE = "express_mode"
    RAPID_FREEZE = "rapid_freeze"
    FRESH_AIR_FILTER = "fresh_air_filter"
    ONE_TOUCH_FILTER = "one_touch_filter"


REFRIGERATION_SELECT_DESC: dict[
    Refrigeration, ThinQSelectEntityDescription
] = {
    Refrigeration.EXPRESS_MODE: ThinQSelectEntityDescription(
        key=Refrigeration.EXPRESS_MODE,
        icon="mdi:snowflake-variant",
        name="Ice Plus",
        translation_key=Refrigeration.EXPRESS_MODE,
    ),
    Refrigeration.RAPID_FREEZE: ThinQSelectEntityDescription(
        key=Refrigeration.RAPID_FREEZE,
        icon="mdi:snowflake",
        name="Quick Freeze",
        translation_key=Refrigeration.RAPID_FREEZE,
    ),
    Refrigeration.FRESH_AIR_FILTER: ThinQSelectEntityDescription(
        key=Refrigeration.FRESH_AIR_FILTER,
        icon="mdi:air-filter",
        name="Fresh Air Filter",
        translation_key=Refrigeration.FRESH_AIR_FILTER,
    ),
}
REFRIGERATION_SENSOR_DESC: dict[
    Refrigeration, ThinQSensorEntityDescription
] = {
    Refrigeration.FRESH_AIR_FILTER: ThinQSensorEntityDescription(
        key=Refrigeration.FRESH_AIR_FILTER,
        icon="mdi:air-filter",
        name="Fresh Air Filter",
        translation_key=Refrigeration.FRESH_AIR_FILTER,
    ),
    Refrigeration.ONE_TOUCH_FILTER: ThinQSensorEntityDescription(
        key=Refrigeration.ONE_TOUCH_FILTER,
        icon="mdi:air-filter",
        name="Fresh Air Filter",
        translation_key=Refrigeration.ONE_TOUCH_FILTER,
    ),
}


@unique
class RemoteControl(StrEnum):
    """Properties in 'remoteControlEnable' module."""

    REMOTE_CONTROL_ENABLED = "remote_control_enabled"


REMOTE_CONTROL_BINARY_SENSOR_DESC: dict[
    RemoteControl, ThinQBinarySensorEntityDescription
] = {
    RemoteControl.REMOTE_CONTROL_ENABLED: ThinQBinarySensorEntityDescription(
        key=RemoteControl.REMOTE_CONTROL_ENABLED,
        icon="mdi:remote",
        name="Remote Start",
        translation_key=RemoteControl.REMOTE_CONTROL_ENABLED,
    ),
}


@unique
class RunState(StrEnum):
    """Properties in 'runState' module."""

    CURRENT_STATE = "current_state"
    COCK_STATE = "cock_state"
    GROWTH_MODE = "growth_mode"
    STERILIZING_STATE = "sterilizing_state"
    WIND_VOLUME = "wind_volume"


RUN_STATE_SENSOR_DESC: dict[RunState, ThinQSensorEntityDescription] = {
    RunState.CURRENT_STATE: ThinQSensorEntityDescription(
        key=RunState.CURRENT_STATE,
        icon="mdi:list-status",
        name="Current status",
        translation_key=RunState.CURRENT_STATE,
    ),
    RunState.COCK_STATE: ThinQSensorEntityDescription(
        key=RunState.COCK_STATE,
        icon="mdi:air-filter",
        name="UVnano",
        translation_key=RunState.COCK_STATE,
    ),
    RunState.STERILIZING_STATE: ThinQSensorEntityDescription(
        key=RunState.STERILIZING_STATE,
        icon="mdi:water-alert-outline",
        name="High-temp sterilization",
        translation_key=RunState.STERILIZING_STATE,
    ),
    RunState.GROWTH_MODE: ThinQSensorEntityDescription(
        key=RunState.GROWTH_MODE,
        icon="mdi:sprout-outline",
        name="Mode",
        translation_key=RunState.GROWTH_MODE,
    ),
    RunState.WIND_VOLUME: ThinQSensorEntityDescription(
        key=RunState.WIND_VOLUME,
        icon="mdi:wind-power-outline",
        name="Wind Speed",
        translation_key=RunState.WIND_VOLUME,
    ),
}


@unique
class Sabbath(StrEnum):
    """Properties in 'sabbath' module."""

    SABBATH_MODE = "sabbath_mode"


SABBATH_BINARY_SENSOR_DESC: dict[
    Sabbath, ThinQBinarySensorEntityDescription
] = {
    Sabbath.SABBATH_MODE: ThinQBinarySensorEntityDescription(
        key=Sabbath.SABBATH_MODE,
        icon="mdi:food-off-outline",
        name="Sabbath",
        translation_key=Sabbath.SABBATH_MODE,
    ),
}


@unique
class Temperature(StrEnum):
    """Properties in 'temperature' module."""

    CURRENT_TEMPERATURE = "current_temperature"
    TARGET_TEMPERATURE = "target_temperature"
    COOL_TARGET_TEMPERATURE = "cool_target_temperature"
    HEAT_TARGET_TEMPERATURE = "heat_target_temperature"
    DAY_TARGET_TEMPERATURE = "day_target_temperature"
    NIGHT_TARGET_TEMPERATURE = "night_target_temperature"
    TEMPERATURE_STATE = "temperatureState"
    UNIT = "temperature_unit"


@unique
class TwoSetTemperature(StrEnum):
    """Properties in 'twoSetTemperature' module."""

    CURRENT_TEMPERATURE = "two_set_current_temperature"
    HEAT_TARGET_TEMPERATURE = "two_set_heat_target_temperature"
    COOL_TARGET_TEMPERATURE = "two_set_cool_target_temperature"
    UNIT = "two_set_temperature_unit"


TEMPERATURE_NUMBER_DESC: dict[Temperature, ThinQNumberEntityDescription] = {
    Temperature.TARGET_TEMPERATURE: ThinQNumberEntityDescription(
        key=Temperature.TARGET_TEMPERATURE,
        icon="mdi:thermometer",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key=Temperature.TARGET_TEMPERATURE,
        property_info=PropertyInfo(
            key=Temperature.TARGET_TEMPERATURE,
            mode=PropertyMode.SELECTIVE,
            children=(
                PropertyInfo(key=f"{Temperature.TARGET_TEMPERATURE}_c"),
                PropertyInfo(key=f"{Temperature.TARGET_TEMPERATURE}_f"),
            ),
            unit_info=PropertyInfo(key=Temperature.UNIT),
            alt_range={"max": 60, "min": 35, "step": 1},
        ),
    ),
}
TEMPERATURE_SENSOR_DESC: dict[Temperature, ThinQSensorEntityDescription] = {
    Temperature.TARGET_TEMPERATURE: ThinQSensorEntityDescription(
        key=Temperature.TARGET_TEMPERATURE,
        icon="mdi:thermometer",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key=Temperature.TARGET_TEMPERATURE,
        property_info=PropertyInfo(
            key=Temperature.TARGET_TEMPERATURE,
            mode=PropertyMode.SELECTIVE,
            children=(
                PropertyInfo(key=f"{Temperature.TARGET_TEMPERATURE}_c"),
                PropertyInfo(key=f"{Temperature.TARGET_TEMPERATURE}_f"),
            ),
            unit_info=PropertyInfo(key=Temperature.UNIT),
        ),
    ),
    Temperature.DAY_TARGET_TEMPERATURE: ThinQSensorEntityDescription(
        key=Temperature.DAY_TARGET_TEMPERATURE,
        icon="mdi:thermometer",
        name="Day Growth Temp.",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=Temperature.DAY_TARGET_TEMPERATURE,
    ),
    Temperature.NIGHT_TARGET_TEMPERATURE: ThinQSensorEntityDescription(
        key=Temperature.NIGHT_TARGET_TEMPERATURE,
        icon="mdi:thermometer",
        name="Night Growth Temp.",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=Temperature.NIGHT_TARGET_TEMPERATURE,
    ),
    Temperature.TEMPERATURE_STATE: ThinQSensorEntityDescription(
        key=Temperature.TEMPERATURE_STATE,
        icon="mdi:thermometer",
        name="Temperature",
        translation_key=Temperature.TEMPERATURE_STATE,
    ),
    Temperature.CURRENT_TEMPERATURE: ThinQSensorEntityDescription(
        key=Temperature.CURRENT_TEMPERATURE,
        icon="mdi:thermometer",
        name="Current Temp.",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=Temperature.CURRENT_TEMPERATURE,
        property_info=PropertyInfo(
            key=Temperature.CURRENT_TEMPERATURE,
            unit_info=PropertyInfo(key=Temperature.UNIT),
        ),
    ),
}


@unique
class Timer(StrEnum):
    """Properties in 'timer' module."""

    ABSOLUTE_TO_START = "absolute_to_start"  # hour, minute
    ABSOLUTE_TO_STOP = "absolute_to_stop"  # hour, minute
    ABSOLUTE_HOUR_TO_START = "absolute_hour_to_start"
    ABSOLUTE_MINUTE_TO_START = "absolute_minute_to_start"
    ABSOLUTE_HOUR_TO_STOP = "absolute_hour_to_stop"
    ABSOLUTE_MINUTE_TO_STOP = "absolute_minute_to_stop"
    RELATIVE_TO_START = "relative_to_start"  # hour, minute
    RELATIVE_TO_START_WM = "relative_to_start_wm"  # seperated translation_key
    RELATIVE_TO_STOP = "relative_to_stop"  # hour, minute
    RELATIVE_TO_STOP_WM = "relative_to_stop_wm"  # seperated translation_key
    RELATIVE_HOUR_TO_START = "relative_hour_to_start"
    RELATIVE_HOUR_TO_START_WM = "relative_hour_to_start_wm"
    RELATIVE_MINUTE_TO_START = "relative_minute_to_start"
    RELATIVE_HOUR_TO_STOP = "relative_hour_to_stop"
    RELATIVE_HOUR_TO_STOP_WM = "relative_hour_to_stop_wm"
    RELATIVE_MINUTE_TO_STOP = "relative_minute_to_stop"
    SLEEP_TIMER_RELATIVE_TO_STOP = "sleep_timer_relative_to_stop"  # h, m
    SLEEP_TIMER_RELATIVE_HOUR_TO_STOP = "sleep_timer_relative_hour_to_stop"
    SLEEP_TIMER_RELATIVE_MINUTE_TO_STOP = "sleep_timer_relative_minute_to_stop"
    REMAIN = "remain"  # hour, minute, second
    REMAIN_HM = "remain_hour_minute"
    REMAIN_MS = "remain_minute_second"
    REMAIN_HOUR = "remain_hour"
    REMAIN_MINUTE = "remain_minute"
    REMAIN_SECOND = "remain_second"
    RUNNING = "running"  # hour, minute
    RUNNING_HOUR = "running_hour"
    RUNNING_MINUTE = "running_minute"
    TARGET = "target"  # hour, minute
    TARGET_HOUR = "target_hour"
    TARGET_MINUTE = "target_minute"
    TARGET_SECOND = "target_second"
    TIMER = "timer"
    TIMER_HOUR = "timer_hour"
    TIMER_MINUTE = "timer_minute"
    TIMER_SECOND = "timer_second"
    TOTAL = "total"  # hour, minute
    TOTAL_HOUR = "total_hour"
    TOTAL_MINUTE = "total_minute"
    ELASPED_DAY_STATE = "elapsed_day_state"
    ELASPED_DAY_TOTAL = "elapsed_day_total"


TIMER_NUMBER_DESC: dict[Timer, ThinQNumberEntityDescription] = {
    Timer.RELATIVE_HOUR_TO_START: ThinQNumberEntityDescription(
        key=Timer.RELATIVE_HOUR_TO_START,
        icon="mdi:timer-edit-outline",
        name="Schedule: Turn On",
        native_unit_of_measurement=UnitOfTime.HOURS,
        translation_key=Timer.RELATIVE_HOUR_TO_START,
        property_info=PropertyInfo(
            key=Timer.RELATIVE_HOUR_TO_START,
            alt_post_method=TIMER_RELATIVE_HOUR_START_METHOD,
        ),
    ),
    Timer.RELATIVE_HOUR_TO_START_WM: ThinQNumberEntityDescription(
        key=Timer.RELATIVE_HOUR_TO_START,
        icon="mdi:timer-edit-outline",
        name="Delay: Starts in",
        native_unit_of_measurement=UnitOfTime.HOURS,
        translation_key=Timer.RELATIVE_HOUR_TO_START_WM,
        property_info=PropertyInfo(
            key=Timer.RELATIVE_HOUR_TO_START,
            modify_minimum_range=True,
            alt_post_method=TIMER_RELATIVE_HOUR_START_METHOD,
        ),
    ),
    Timer.RELATIVE_MINUTE_TO_START: ThinQNumberEntityDescription(
        key=Timer.RELATIVE_MINUTE_TO_START,
        icon="mdi:timer-edit-outline",
        name="Schedule: Turn On",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        translation_key=Timer.RELATIVE_MINUTE_TO_START,
        property_info=PropertyInfo(
            key=Timer.RELATIVE_MINUTE_TO_START,
            alt_post_method=TIMER_RELATIVE_MINUTE_START_METHOD,
        ),
    ),
    Timer.RELATIVE_HOUR_TO_STOP: ThinQNumberEntityDescription(
        key=Timer.RELATIVE_HOUR_TO_STOP,
        icon="mdi:timer-edit-outline",
        name="Schedule: Turn Off",
        native_unit_of_measurement=UnitOfTime.HOURS,
        translation_key=Timer.RELATIVE_HOUR_TO_STOP,
        property_info=PropertyInfo(
            key=Timer.RELATIVE_HOUR_TO_STOP,
            alt_post_method=TIMER_RELATIVE_HOUR_STOP_METHOD,
        ),
    ),
    Timer.RELATIVE_HOUR_TO_STOP_WM: ThinQNumberEntityDescription(
        key=Timer.RELATIVE_HOUR_TO_STOP,
        icon="mdi:timer-edit-outline",
        name="Delay: Ends in",
        native_unit_of_measurement=UnitOfTime.HOURS,
        translation_key=Timer.RELATIVE_HOUR_TO_STOP_WM,
        property_info=PropertyInfo(
            key=Timer.RELATIVE_HOUR_TO_STOP,
            modify_minimum_range=True,
            alt_post_method=TIMER_RELATIVE_HOUR_STOP_METHOD,
        ),
    ),
    Timer.RELATIVE_MINUTE_TO_STOP: ThinQNumberEntityDescription(
        key=Timer.RELATIVE_MINUTE_TO_STOP,
        icon="mdi:timer-edit-outline",
        name="Schedule: Turn Off",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        translation_key=Timer.RELATIVE_MINUTE_TO_STOP,
        property_info=PropertyInfo(
            key=Timer.RELATIVE_MINUTE_TO_STOP,
            alt_post_method=TIMER_RELATIVE_MINUTE_STOP_METHOD,
        ),
    ),
    Timer.REMAIN_HOUR: ThinQNumberEntityDescription(
        key=Timer.REMAIN_HOUR,
        icon="mdi:timer-edit-outline",
        name="Time Remaining",
        native_unit_of_measurement=UnitOfTime.HOURS,
        translation_key=Timer.REMAIN_HOUR,
    ),
    Timer.REMAIN_MINUTE: ThinQNumberEntityDescription(
        key=Timer.REMAIN_MINUTE,
        icon="mdi:timer-edit-outline",
        name="Time Remaining",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        translation_key=Timer.REMAIN_MINUTE,
    ),
    Timer.SLEEP_TIMER_RELATIVE_HOUR_TO_STOP: ThinQNumberEntityDescription(
        key=Timer.SLEEP_TIMER_RELATIVE_HOUR_TO_STOP,
        icon="mdi:bed-clock",
        name="Sleep Timer",
        native_unit_of_measurement=UnitOfTime.HOURS,
        translation_key=Timer.SLEEP_TIMER_RELATIVE_HOUR_TO_STOP,
        property_info=PropertyInfo(
            key=Timer.SLEEP_TIMER_RELATIVE_HOUR_TO_STOP,
            alt_post_method=TIMER_SLEEP_TIMER_RELATIVE_HOUR_STOP_METHOD,
        ),
    ),
    Timer.SLEEP_TIMER_RELATIVE_MINUTE_TO_STOP: ThinQNumberEntityDescription(
        key=Timer.SLEEP_TIMER_RELATIVE_MINUTE_TO_STOP,
        icon="mdi:bed-clock",
        name="Sleep Timer",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        translation_key=Timer.SLEEP_TIMER_RELATIVE_MINUTE_TO_STOP,
        property_info=PropertyInfo(
            key=Timer.SLEEP_TIMER_RELATIVE_MINUTE_TO_STOP,
            alt_post_method=TIMER_SLEEP_TIMER_RELATIVE_MINUTE_STOP_METHOD,
        ),
    ),
}
TIMER_SENSOR_DESC: dict[Timer, ThinQSensorEntityDescription] = {
    Timer.RELATIVE_TO_START: ThinQSensorEntityDescription(
        key=Timer.RELATIVE_TO_START,
        icon="mdi:clock-time-three-outline",
        name="Schedule: Turn On",
        translation_key=Timer.RELATIVE_TO_START,
        property_info=PropertyInfo(
            key=Timer.RELATIVE_TO_START,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(
                    key=Timer.RELATIVE_HOUR_TO_START,
                    alt_validate_creation=VALIDATE_CREATION_READABLE,
                ),
                PropertyInfo(
                    key=Timer.RELATIVE_MINUTE_TO_START,
                    alt_validate_creation=VALIDATE_CREATION_READABLE,
                ),
            ),
            value_formatter=TIMER_COMBINED_SENSOR_FORMATTER,
            alt_validate_creation=VALIDATE_CREATION_READABLE,
        ),
    ),
    Timer.RELATIVE_TO_START_WM: ThinQSensorEntityDescription(
        key=Timer.RELATIVE_TO_START,
        icon="mdi:clock-time-three-outline",
        name="Delay: Starts in",
        translation_key=Timer.RELATIVE_TO_START_WM,
        property_info=PropertyInfo(
            key=Timer.RELATIVE_TO_START,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(
                    key=Timer.RELATIVE_HOUR_TO_START,
                    alt_validate_creation=VALIDATE_CREATION_READABLE,
                ),
                PropertyInfo(
                    key=Timer.RELATIVE_MINUTE_TO_START,
                    alt_validate_creation=VALIDATE_CREATION_READABLE,
                ),
            ),
            value_formatter=TIMER_COMBINED_SENSOR_FORMATTER,
            alt_validate_creation=VALIDATE_CREATION_READABLE,
        ),
    ),
    Timer.RELATIVE_TO_STOP: ThinQSensorEntityDescription(
        key=Timer.RELATIVE_TO_STOP,
        icon="mdi:clock-time-three-outline",
        name="Schedule: Turn Off",
        translation_key=Timer.RELATIVE_TO_STOP,
        property_info=PropertyInfo(
            key=Timer.RELATIVE_TO_STOP,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(
                    key=Timer.RELATIVE_HOUR_TO_STOP,
                    alt_validate_creation=VALIDATE_CREATION_READABLE,
                ),
                PropertyInfo(
                    key=Timer.RELATIVE_MINUTE_TO_STOP,
                    alt_validate_creation=VALIDATE_CREATION_READABLE,
                ),
            ),
            value_formatter=TIMER_COMBINED_SENSOR_FORMATTER,
            alt_validate_creation=VALIDATE_CREATION_READABLE,
        ),
    ),
    Timer.RELATIVE_TO_STOP_WM: ThinQSensorEntityDescription(
        key=Timer.RELATIVE_TO_STOP,
        icon="mdi:clock-time-three-outline",
        name="Delay: Ends in",
        translation_key=Timer.RELATIVE_TO_STOP_WM,
        property_info=PropertyInfo(
            key=Timer.RELATIVE_TO_STOP,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(
                    key=Timer.RELATIVE_HOUR_TO_STOP,
                    alt_validate_creation=VALIDATE_CREATION_READABLE,
                ),
                PropertyInfo(
                    key=Timer.RELATIVE_MINUTE_TO_STOP,
                    alt_validate_creation=VALIDATE_CREATION_READABLE,
                ),
            ),
            value_formatter=TIMER_COMBINED_SENSOR_FORMATTER,
            alt_validate_creation=VALIDATE_CREATION_READABLE,
        ),
    ),
    Timer.SLEEP_TIMER_RELATIVE_TO_STOP: ThinQSensorEntityDescription(
        key=Timer.SLEEP_TIMER_RELATIVE_TO_STOP,
        icon="mdi:bed-clock",
        name="Sleep Timer",
        translation_key=Timer.SLEEP_TIMER_RELATIVE_TO_STOP,
        property_info=PropertyInfo(
            key=Timer.SLEEP_TIMER_RELATIVE_TO_STOP,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(
                    key=Timer.SLEEP_TIMER_RELATIVE_HOUR_TO_STOP,
                    alt_validate_creation=VALIDATE_CREATION_READABLE,
                ),
                PropertyInfo(
                    key=Timer.SLEEP_TIMER_RELATIVE_MINUTE_TO_STOP,
                    alt_validate_creation=VALIDATE_CREATION_READABLE,
                ),
            ),
            value_formatter=TIMER_COMBINED_SENSOR_FORMATTER,
            alt_validate_creation=VALIDATE_CREATION_READABLE,
        ),
    ),
    Timer.ABSOLUTE_TO_START: ThinQSensorEntityDescription(
        key=Timer.ABSOLUTE_TO_START,
        icon="mdi:clock-time-three-outline",
        name="Schedule: Turn On",
        translation_key=Timer.ABSOLUTE_TO_START,
        property_info=PropertyInfo(
            key=Timer.ABSOLUTE_TO_START,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(
                    key=Timer.ABSOLUTE_HOUR_TO_START,
                    alt_validate_creation=VALIDATE_CREATION_READABLE,
                ),
                PropertyInfo(
                    key=Timer.ABSOLUTE_MINUTE_TO_START,
                    alt_validate_creation=VALIDATE_CREATION_READABLE,
                ),
            ),
            value_formatter=TIMER_COMBINED_2_SENSOR_FORMATTER,
            alt_validate_creation=VALIDATE_CREATION_READABLE,
        ),
    ),
    Timer.ABSOLUTE_TO_STOP: ThinQSensorEntityDescription(
        key=Timer.ABSOLUTE_TO_STOP,
        icon="mdi:clock-time-three-outline",
        name="Schedule: Turn Off",
        translation_key=Timer.ABSOLUTE_TO_STOP,
        property_info=PropertyInfo(
            key=Timer.ABSOLUTE_TO_STOP,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(
                    key=Timer.ABSOLUTE_HOUR_TO_STOP,
                    alt_validate_creation=VALIDATE_CREATION_READABLE,
                ),
                PropertyInfo(
                    key=Timer.ABSOLUTE_MINUTE_TO_STOP,
                    alt_validate_creation=VALIDATE_CREATION_READABLE,
                ),
            ),
            value_formatter=TIMER_COMBINED_2_SENSOR_FORMATTER,
            alt_validate_creation=VALIDATE_CREATION_READABLE,
        ),
    ),
    Timer.REMAIN: ThinQSensorEntityDescription(
        key=Timer.REMAIN,
        icon="mdi:timer-sand",
        name="Time Remaining",
        translation_key=Timer.REMAIN,
        property_info=PropertyInfo(
            key=Timer.REMAIN,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(key=Timer.REMAIN_HOUR),
                PropertyInfo(key=Timer.REMAIN_MINUTE),
                PropertyInfo(key=Timer.REMAIN_SECOND),
            ),
            value_formatter=TIMER_COMBINED_SENSOR_FORMATTER,
        ),
    ),
    Timer.REMAIN_HM: ThinQSensorEntityDescription(
        key=Timer.REMAIN_HM,
        icon="mdi:timer-sand",
        name="Time Remaining",
        translation_key=Timer.REMAIN,
        property_info=PropertyInfo(
            key=Timer.REMAIN_HM,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(
                    key=Timer.REMAIN_HOUR,
                    alt_validate_creation=VALIDATE_CREATION_READABLE,
                ),
                PropertyInfo(
                    key=Timer.REMAIN_MINUTE,
                    alt_validate_creation=VALIDATE_CREATION_READABLE,
                ),
            ),
            value_formatter=TIMER_COMBINED_SENSOR_FORMATTER,
            alt_validate_creation=VALIDATE_CREATION_READABLE,
        ),
    ),
    Timer.REMAIN_MS: ThinQSensorEntityDescription(
        key=Timer.REMAIN_MS,
        icon="mdi:timer-sand",
        name="Time Remaining",
        translation_key=Timer.REMAIN,
        property_info=PropertyInfo(
            key=Timer.REMAIN,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(key=Timer.REMAIN_MINUTE),
                PropertyInfo(key=Timer.REMAIN_SECOND),
            ),
            value_formatter=TIMER_COMBINED_SENSOR_FORMATTER,
        ),
    ),
    Timer.TARGET: ThinQSensorEntityDescription(
        key=Timer.TARGET,
        icon="mdi:clock-time-three-outline",
        name="Cook time",
        translation_key=Timer.TARGET,
        property_info=PropertyInfo(
            key=Timer.TARGET,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(
                    key=Timer.TARGET_HOUR,
                    alt_validate_creation=VALIDATE_CREATION_READABLE,
                ),
                PropertyInfo(
                    key=Timer.TARGET_MINUTE,
                    alt_validate_creation=VALIDATE_CREATION_READABLE,
                ),
            ),
            value_formatter=TIMER_COMBINED_SENSOR_FORMATTER,
            alt_validate_creation=VALIDATE_CREATION_READABLE,
        ),
    ),
    Timer.RUNNING: ThinQSensorEntityDescription(
        key=Timer.RUNNING,
        icon="mdi:timer-play-outline",
        name="Time Running",
        translation_key=Timer.RUNNING,
        property_info=PropertyInfo(
            key=Timer.RUNNING,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(key=Timer.RUNNING_HOUR),
                PropertyInfo(key=Timer.RUNNING_MINUTE),
            ),
            value_formatter=TIMER_COMBINED_SENSOR_FORMATTER,
        ),
    ),
    Timer.TOTAL: ThinQSensorEntityDescription(
        key=Timer.TOTAL,
        icon="mdi:timer-play-outline",
        name="Time Total",
        translation_key=Timer.TOTAL,
        property_info=PropertyInfo(
            key=Timer.TOTAL,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(key=Timer.TOTAL_HOUR),
                PropertyInfo(key=Timer.TOTAL_MINUTE),
            ),
            value_formatter=TIMER_COMBINED_SENSOR_FORMATTER,
        ),
    ),
    Timer.ELASPED_DAY_STATE: ThinQSensorEntityDescription(
        key=Timer.ELASPED_DAY_STATE,
        icon="mdi:calendar-range-outline",
        name="Brewing period",
        native_unit_of_measurement=UnitOfTime.DAYS,
        translation_key=Timer.ELASPED_DAY_STATE,
    ),
    Timer.ELASPED_DAY_TOTAL: ThinQSensorEntityDescription(
        key=Timer.ELASPED_DAY_TOTAL,
        icon="mdi:calendar-range-outline",
        name="Brewing Duration",
        native_unit_of_measurement=UnitOfTime.DAYS,
        translation_key=Timer.ELASPED_DAY_TOTAL,
    ),
}
TIMER_TIME_DESC: dict[Timer, ThinQTimeEntityDescription] = {
    Timer.ABSOLUTE_TO_START: ThinQTimeEntityDescription(
        key=Timer.ABSOLUTE_TO_START,
        icon="mdi:timer-edit-outline",
        name="Schedule:On",
        translation_key=Timer.ABSOLUTE_TO_START,
        property_info=PropertyInfo(
            key=Timer.ABSOLUTE_TO_START,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(key=Timer.ABSOLUTE_HOUR_TO_START),
                PropertyInfo(key=Timer.ABSOLUTE_MINUTE_TO_START),
            ),
            value_formatter=TIMER_COMBINED_TIME_FORMATTER,
            alt_post_method=TIMER_ABSOLUTE_TIME_START_METHOD,
        ),
    ),
    Timer.ABSOLUTE_TO_STOP: ThinQTimeEntityDescription(
        key=Timer.ABSOLUTE_TO_STOP,
        icon="mdi:timer-edit-outline",
        name="Schedule:Off",
        translation_key=Timer.ABSOLUTE_TO_STOP,
        property_info=PropertyInfo(
            key=Timer.ABSOLUTE_TO_STOP,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(key=Timer.ABSOLUTE_HOUR_TO_STOP),
                PropertyInfo(key=Timer.ABSOLUTE_MINUTE_TO_STOP),
            ),
            value_formatter=TIMER_COMBINED_TIME_FORMATTER,
            alt_post_method=TIMER_ABSOLUTE_TIME_STOP_METHOD,
        ),
    ),
    Timer.TARGET: ThinQTimeEntityDescription(
        key=Timer.TARGET,
        icon="mdi:timer-edit-outline",
        name="Cook time",
        translation_key=Timer.TARGET,
        property_info=PropertyInfo(
            key=Timer.TARGET,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(key=Timer.TARGET_HOUR),
                PropertyInfo(key=Timer.TARGET_MINUTE),
            ),
            value_formatter=TIMER_COMBINED_TIME_FORMATTER,
            alt_post_method=TIMER_ABSOLUTE_TIME_STOP_METHOD,
        ),
    ),
    Timer.TIMER: ThinQTimeEntityDescription(
        key=Timer.TIMER,
        icon="mdi:timer-edit-outline",
        name="Timer",
        translation_key=Timer.TIMER,
        property_info=PropertyInfo(
            key=Timer.TIMER,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(key=Timer.TIMER_HOUR),
                PropertyInfo(key=Timer.TIMER_MINUTE),
            ),
            value_formatter=TIMER_COMBINED_TIME_FORMATTER,
            alt_post_method=TIMER_ABSOLUTE_TIME_STOP_METHOD,
        ),
    ),
}
TIMER_TEXT_DESC: dict[Timer, ThinQTextEntityDescription] = {
    Timer.ABSOLUTE_TO_START: ThinQTextEntityDescription(
        key=Timer.ABSOLUTE_TO_START,
        icon="mdi:timer-edit-outline",
        name="Schedule: Turn On",
        translation_key=Timer.ABSOLUTE_TO_START,
        property_info=PropertyInfo(
            key=Timer.ABSOLUTE_TO_START,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(key=Timer.ABSOLUTE_HOUR_TO_START),
                PropertyInfo(key=Timer.ABSOLUTE_MINUTE_TO_START),
            ),
            value_formatter=TIMER_COMBINED_TEXT_FORMATTER,
            alt_text_hint="Input format 24-hour clock",
            value_converter=VALUE_TO_TIME_TEXT_CONVERTER,
            alt_post_method=TIMER_ABSOLUTE_TEXT_START_METHOD,
        ),
    ),
    Timer.ABSOLUTE_TO_STOP: ThinQTextEntityDescription(
        key=Timer.ABSOLUTE_TO_STOP,
        icon="mdi:timer-edit-outline",
        name="Schedule: Turn Off",
        translation_key=Timer.ABSOLUTE_TO_STOP,
        property_info=PropertyInfo(
            key=Timer.ABSOLUTE_TO_STOP,
            mode=PropertyMode.COMBINED,
            children=(
                PropertyInfo(key=Timer.ABSOLUTE_HOUR_TO_STOP),
                PropertyInfo(key=Timer.ABSOLUTE_MINUTE_TO_STOP),
            ),
            value_formatter=TIMER_COMBINED_TEXT_FORMATTER,
            alt_text_hint="Input format 24-hour clock",
            value_converter=VALUE_TO_TIME_TEXT_CONVERTER,
            alt_post_method=TIMER_ABSOLUTE_TEXT_STOP_METHOD,
        ),
    ),
}


@unique
class Ventilation(StrEnum):
    """Properties in 'ventilation' module."""

    FAN_SPEED = "fan_speed"


VENTILATION_NUMBER_DESC: dict[Ventilation, ThinQNumberEntityDescription] = {
    Ventilation.FAN_SPEED: ThinQNumberEntityDescription(
        key=Ventilation.FAN_SPEED,
        icon="mdi:wind-power-outline",
        name="Fan",
        translation_key=Ventilation.FAN_SPEED,
    ),
}


@unique
class WaterFilterInfo(StrEnum):
    """Properties in 'waterFilterInfo' module."""

    USED_TIME = "used_time"


WATER_FILTER_INFO_SENSOR_DESC: dict[
    WaterFilterInfo, ThinQSensorEntityDescription
] = {
    WaterFilterInfo.USED_TIME: ThinQSensorEntityDescription(
        key=WaterFilterInfo.USED_TIME,
        icon="mdi:air-filter",
        name="Water Filter",
        native_unit_of_measurement=UnitOfTime.MONTHS,
        translation_key="water_filter_used_time",
    ),
}


@unique
class WaterInfo(StrEnum):
    """Properties in 'waterInfo' module."""

    WATER_TYPE = "water_type"


WATER_INFO_SENSOR_DESC: dict[WaterInfo, ThinQSensorEntityDescription] = {
    WaterInfo.WATER_TYPE: ThinQSensorEntityDescription(
        key=WaterInfo.WATER_TYPE,
        icon="mdi:water",
        name="Type",
        translation_key=WaterInfo.WATER_TYPE,
    ),
}

# Common Description
REMOTE_CONTROL_BINARY_SENSOR: tuple[
    ThinQBinarySensorEntityDescription, ...
] = (REMOTE_CONTROL_BINARY_SENSOR_DESC[RemoteControl.REMOTE_CONTROL_ENABLED],)
ABSOLUTE_TIMER_TIME: tuple[ThinQTimeEntityDescription, ...] = (
    TIMER_TIME_DESC[Timer.ABSOLUTE_TO_START],
    TIMER_TIME_DESC[Timer.ABSOLUTE_TO_STOP],
)

# AIRCONDITIONER Description
AIRCONDITIONER_CLIMATE: tuple[ThinQClimateEntityDescription, ...] = (
    ThinQClimateEntityDescription(
        key="climate",
        icon="mdi:air-conditioner",
        name=None,
        translation_key="translation_climate",
        property_info=PropertyInfo(
            key="air_conditioner_climate",
            mode=PropertyMode.FEATURED,
            children=(
                PropertyInfo(
                    key=Operation.AIR_CON_OPERATION_MODE,
                    feature=PropertyFeature.POWER,
                ),
                PropertyInfo(
                    key=Temperature.CURRENT_TEMPERATURE,
                    feature=PropertyFeature.CURRENT_TEMP,
                    unit_info=PropertyInfo(key=Temperature.UNIT),
                ),
                PropertyInfo(
                    key=Temperature.TARGET_TEMPERATURE,
                    feature=PropertyFeature.TARGET_TEMP,
                    unit_info=PropertyInfo(key=Temperature.UNIT),
                ),
                PropertyInfo(
                    key=Temperature.COOL_TARGET_TEMPERATURE,
                    feature=PropertyFeature.COOL_TARGET_TEMP,
                    unit_info=PropertyInfo(key=Temperature.UNIT),
                ),
                PropertyInfo(
                    key=Temperature.HEAT_TARGET_TEMPERATURE,
                    feature=PropertyFeature.HEAT_TARGET_TEMP,
                    unit_info=PropertyInfo(key=Temperature.UNIT),
                ),
                PropertyInfo(
                    key=TwoSetTemperature.CURRENT_TEMPERATURE,
                    feature=PropertyFeature.TWO_SET_CURRENT_TEMP,
                    unit_info=PropertyInfo(key=TwoSetTemperature.UNIT),
                ),
                PropertyInfo(
                    key=TwoSetTemperature.COOL_TARGET_TEMPERATURE,
                    feature=PropertyFeature.TWO_SET_COOL_TARGET_TEMP,
                    unit_info=PropertyInfo(key=TwoSetTemperature.UNIT),
                ),
                PropertyInfo(
                    key=TwoSetTemperature.HEAT_TARGET_TEMPERATURE,
                    feature=PropertyFeature.TWO_SET_HEAT_TARGET_TEMP,
                    unit_info=PropertyInfo(key=TwoSetTemperature.UNIT),
                ),
                PropertyInfo(
                    key=AirFlow.WIND_STRENGTH,
                    mode=PropertyMode.SELECTIVE,
                    feature=PropertyFeature.FAN_MODE,
                    children=(
                        PropertyInfo(
                            key=AirFlow.WIND_STEP,
                            alt_options_provider=RANGE_TO_OPTIONS_PROVIDER,
                            value_converter=VALUE_TO_INT_CONVERTER,
                            value_formatter=VALUE_TO_STR_CONVERTER,
                        ),
                    ),
                ),
                PropertyInfo(
                    key=JobMode.CURRENT_JOB_MODE,
                    feature=PropertyFeature.HVAC_MODE,
                ),
                PropertyInfo(
                    key=AirQuality.HUMIDITY,
                    feature=PropertyFeature.CURRENT_HUMIDITY,
                ),
            ),
        ),
    ),
)
AIRCONDITIONER_NUMBER: tuple[ThinQNumberEntityDescription, ...] = (
    TIMER_NUMBER_DESC[Timer.RELATIVE_HOUR_TO_START],
    TIMER_NUMBER_DESC[Timer.RELATIVE_HOUR_TO_STOP],
    TIMER_NUMBER_DESC[Timer.SLEEP_TIMER_RELATIVE_HOUR_TO_STOP],
)
AIRCONDITIONER_SELECT: tuple[ThinQSelectEntityDescription, ...] = (
    AIR_QUALITY_SELECT_DESC[AirQuality.MONITORING_ENABLED],
    OPERATION_SELECT_DESC[Operation.AIR_CLEAN_OPERATION_MODE],
    POWER_SAVE_SELECT_DESC[PowerSave.POWER_SAVE_ENABLED],
)
AIRCONDITIONER_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    AIR_QUALITY_SENSOR_DESC[AirQuality.PM1],
    AIR_QUALITY_SENSOR_DESC[AirQuality.PM2],
    AIR_QUALITY_SENSOR_DESC[AirQuality.PM10],
    AIR_QUALITY_SENSOR_DESC[AirQuality.HUMIDITY],
    AIR_QUALITY_SENSOR_DESC[AirQuality.ODOR],
    AIR_QUALITY_SENSOR_DESC[AirQuality.TOTAL_POLLUTION],
    COMMON_SENSOR_DESC[Common.NOTIFICATION],
    TIMER_SENSOR_DESC[Timer.RELATIVE_TO_START],
    TIMER_SENSOR_DESC[Timer.RELATIVE_TO_STOP],
    TIMER_SENSOR_DESC[Timer.SLEEP_TIMER_RELATIVE_TO_STOP],
    FILTER_INFO_SENSOR_DESC[FilterInfo.FILTER_LIFE_TIME],
)
AIRCONDITIONER_TEXT: tuple[ThinQTextEntityDescription, ...] = (
    TIMER_TEXT_DESC[Timer.ABSOLUTE_TO_START],
    TIMER_TEXT_DESC[Timer.ABSOLUTE_TO_STOP],
)
# AIR_PURIFIER_FAN Description
AIR_PURIFIER_FAN_NUMBER: tuple[ThinQNumberEntityDescription, ...] = (
    AIR_FLOW_NUMBER_DESC[AirFlow.WIND_TEMPERATURE],
    TIMER_NUMBER_DESC[Timer.SLEEP_TIMER_RELATIVE_HOUR_TO_STOP],
)
AIR_PURIFIER_FAN_SELECT: tuple[ThinQSelectEntityDescription, ...] = (
    AIR_FLOW_SELECT_DESC[AirFlow.WIND_STRENGTH],
    AIR_FLOW_SELECT_DESC[AirFlow.WIND_ANGLE],
    AIR_FLOW_SELECT_DESC[AirFlow.WARM_MODE],
    DISPLAY_SELECT_DESC[Display.LIGHT],
    JOB_MODE_SELECT_DESC[JobMode.CURRENT_JOB_MODE],
    MISC_SELECT_DESC[Misc.UV_NANO],
)
AIR_PURIFIER_FAN_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    AIR_QUALITY_SENSOR_DESC[AirQuality.PM1],
    AIR_QUALITY_SENSOR_DESC[AirQuality.PM2],
    AIR_QUALITY_SENSOR_DESC[AirQuality.PM10],
    AIR_QUALITY_SENSOR_DESC[AirQuality.HUMIDITY],
    AIR_QUALITY_SENSOR_DESC[AirQuality.ODOR],
    AIR_QUALITY_SENSOR_DESC[AirQuality.TEMPERATURE],
    AIR_QUALITY_SENSOR_DESC[AirQuality.TOTAL_POLLUTION],
    AIR_QUALITY_SENSOR_DESC[AirQuality.MONITORING_ENABLED],
    COMMON_SENSOR_DESC[Common.NOTIFICATION],
    TIMER_SENSOR_DESC[Timer.SLEEP_TIMER_RELATIVE_TO_STOP],
)
AIR_PURIFIER_FAN_SWITCH: tuple[ThinQSwitchEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[Operation.AIR_FAN_OPERATION_MODE],
)
AIR_PURIFIER_FAN_TEXT: tuple[ThinQTextEntityDescription, ...] = (
    TIMER_TEXT_DESC[Timer.ABSOLUTE_TO_START],
    TIMER_TEXT_DESC[Timer.ABSOLUTE_TO_STOP],
)

# AIRPURIFIER Description
AIRPURIFIER_SELECT: tuple[ThinQSelectEntityDescription, ...] = (
    AIR_FLOW_SELECT_DESC[AirFlow.WIND_STRENGTH],
    JOB_MODE_SELECT_DESC[JobMode.CURRENT_JOB_MODE],
)
AIRPURIFIER_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    AIR_QUALITY_SENSOR_DESC[AirQuality.PM1],
    AIR_QUALITY_SENSOR_DESC[AirQuality.PM2],
    AIR_QUALITY_SENSOR_DESC[AirQuality.PM10],
    AIR_QUALITY_SENSOR_DESC[AirQuality.HUMIDITY],
    AIR_QUALITY_SENSOR_DESC[AirQuality.ODOR],
    AIR_QUALITY_SENSOR_DESC[AirQuality.TOTAL_POLLUTION],
    AIR_QUALITY_SENSOR_DESC[AirQuality.MONITORING_ENABLED],
    COMMON_SENSOR_DESC[Common.NOTIFICATION],
    JOB_MODE_SENSOR_DESC[JobMode.CURRENT_JOB_MODE],
    JOB_MODE_SENSOR_DESC[JobMode.PERSONALIZATION_MODE],
)
AIRPURIFIER_SWITCH: tuple[ThinQSwitchEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[Operation.AIR_PURIFIER_OPERATION_MODE],
)
AIRPURIFIER_TEXT: tuple[ThinQTextEntityDescription, ...] = (
    TIMER_TEXT_DESC[Timer.ABSOLUTE_TO_START],
    TIMER_TEXT_DESC[Timer.ABSOLUTE_TO_STOP],
)

# CEILING_FAN Description
CEILING_FAN_FAN: tuple[ThinQFanEntityDescription, ...] = (
    ThinQFanEntityDescription(
        key="fan",
        icon="mdi:ceiling-fan",
        name=None,
        translation_key="translation_fan",
        property_info=PropertyInfo(
            key="ceiling_fan",
            mode=PropertyMode.FEATURED,
            children=(
                PropertyInfo(
                    key=Operation.CEILING_FAN_OPERATION_MODE,
                    feature=PropertyFeature.POWER,
                ),
                PropertyInfo(
                    key=AirFlow.WIND_STRENGTH,
                    feature=PropertyFeature.FAN_MODE,
                ),
            ),
        ),
    ),
)

# COOKTOP Description
COOKTOP_BUTTON: tuple[ThinQButtonEntityDescription, ...] = (
    OPERATION_BUTTON_DESC[Operation.OPERATION_MODE],
)
COOKTOP_NUMBER: tuple[ThinQNumberEntityDescription, ...] = (
    POWER_NUMBER_DESC[Power.POWER_LEVEL],
    TIMER_NUMBER_DESC[Timer.REMAIN_HOUR],
    TIMER_NUMBER_DESC[Timer.REMAIN_MINUTE],
)
COOKTOP_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    RUN_STATE_SENSOR_DESC[RunState.CURRENT_STATE],
    POWER_SENSOR_DESC[Power.POWER_LEVEL],
    TIMER_SENSOR_DESC[Timer.REMAIN_HM],
)

# DEHUMIDIFIER Description
DEHUMIDIFIER_HUMIDIFIER: tuple[ThinQHumidifierEntityDescription, ...] = (
    ThinQHumidifierEntityDescription(
        key="dehumidifier",
        icon="mdi:water-remove-outline",
        name=None,
        device_class=HumidifierDeviceClass.DEHUMIDIFIER,
        translation_key="translation_dehumidifier",
        property_info=PropertyInfo(
            key="dehumidifier",
            mode=PropertyMode.FEATURED,
            children=(
                PropertyInfo(
                    key=Operation.DEHUMIDIFIER_OPERATION_MODE,
                    feature=PropertyFeature.POWER,
                ),
                PropertyInfo(
                    key=JobMode.CURRENT_JOB_MODE,
                    feature=PropertyFeature.OP_MODE,
                ),
                PropertyInfo(
                    key=Humidity.CURRENT_HUMIDITY,
                    feature=PropertyFeature.CURRENT_HUMIDITY,
                ),
            ),
        ),
    ),
)
DEHUMIDIFIER_SELECT: tuple[ThinQSelectEntityDescription, ...] = (
    AIR_FLOW_SELECT_DESC[AirFlow.WIND_STRENGTH],
)
DEHUMIDIFIER_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    COMMON_SENSOR_DESC[Common.NOTIFICATION],
    JOB_MODE_SENSOR_DESC[JobMode.CURRENT_JOB_MODE],
    HUMIDITY_SENSOR_DESC[Humidity.CURRENT_HUMIDITY],
)
DEHUMIDIFIER_SWITCH: tuple[ThinQSwitchEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[Operation.DEHUMIDIFIER_OPERATION_MODE],
)

# DISH_WASHER Description
DISH_WASHER_BINARY_SENSOR: tuple[ThinQBinarySensorEntityDescription, ...] = (
    DISH_WASHING_STATUS_BINARY_SENSOR_DESC[DishWashingStatus.RINSE_REFILL],
    REMOTE_CONTROL_BINARY_SENSOR_DESC[RemoteControl.REMOTE_CONTROL_ENABLED],
)
DISH_WASHER_SELECT: tuple[ThinQSelectEntityDescription, ...] = (
    OPERATION_SELECT_DESC[Operation.DISH_WASHER_OPERATION_MODE],
)
DISH_WASHER_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    COMMON_SENSOR_DESC[Common.ERROR],
    COMMON_SENSOR_DESC[Common.NOTIFICATION],
    DISH_WASHING_COURSE_SENSOR_DESC[
        DishWashingCourse.CURRENT_DISH_WASHING_COURSE
    ],
    DOOR_STATUS_SENSOR_DESC[DoorStatus.DOOR_STATE],
    PREFERENCE_SENSOR_DESC[Preference.RINSE_LEVEL],
    PREFERENCE_SENSOR_DESC[Preference.SOFTENING_LEVEL],
    PREFERENCE_SENSOR_DESC[Preference.M_C_REMINDER],
    PREFERENCE_SENSOR_DESC[Preference.SIGNAL_LEVEL],
    PREFERENCE_SENSOR_DESC[Preference.CLEAN_L_REMINDER],
    RUN_STATE_SENSOR_DESC[RunState.CURRENT_STATE],
    TIMER_SENSOR_DESC[Timer.RELATIVE_TO_START_WM],
    TIMER_SENSOR_DESC[Timer.REMAIN_HM],
    TIMER_SENSOR_DESC[Timer.TOTAL],
)

# DRYER Description
DRYER_NUMBER: tuple[ThinQNumberEntityDescription, ...] = (
    TIMER_NUMBER_DESC[Timer.RELATIVE_HOUR_TO_START_WM],
    TIMER_NUMBER_DESC[Timer.RELATIVE_HOUR_TO_STOP_WM],
)
DRYER_SELECT: tuple[ThinQSelectEntityDescription, ...] = (
    OPERATION_SELECT_DESC[Operation.DRYER_OPERATION_MODE],
)
DRYER_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    COMMON_SENSOR_DESC[Common.ERROR],
    COMMON_SENSOR_DESC[Common.NOTIFICATION],
    RUN_STATE_SENSOR_DESC[RunState.CURRENT_STATE],
    TIMER_SENSOR_DESC[Timer.REMAIN_HM],
    TIMER_SENSOR_DESC[Timer.RELATIVE_TO_START],
    TIMER_SENSOR_DESC[Timer.RELATIVE_TO_STOP_WM],
    TIMER_SENSOR_DESC[Timer.TOTAL],
)


# HOME_BREW Description
HOME_BREW_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    RECIPE_SENSOR_DESC[Recipe.RECIPE_NAME],
    RECIPE_SENSOR_DESC[Recipe.WORT_INFO],
    RECIPE_SENSOR_DESC[Recipe.YEAST_INFO],
    RECIPE_SENSOR_DESC[Recipe.HOP_OIL_INFO],
    RECIPE_SENSOR_DESC[Recipe.FLAVOR_INFO],
    RECIPE_SENSOR_DESC[Recipe.BEER_REMAIN],
    RUN_STATE_SENSOR_DESC[RunState.CURRENT_STATE],
    TIMER_SENSOR_DESC[Timer.ELASPED_DAY_STATE],
    TIMER_SENSOR_DESC[Timer.ELASPED_DAY_TOTAL],
)

# HOOD Description
HOOD_NUMBER: tuple[ThinQNumberEntityDescription, ...] = (
    LAMP_NUMBER_DESC[Lamp.LAMP_BRIGHTNESS],
    VENTILATION_NUMBER_DESC[Ventilation.FAN_SPEED],
)
HOOD_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    OPERATION_SENSOR_DESC[Operation.HOOD_OPERATION_MODE],
    TIMER_SENSOR_DESC[Timer.REMAIN_MS],
)

# HUMIDIFIER Description
HUMIDIFIER_HUMIDIFIER: tuple[ThinQHumidifierEntityDescription, ...] = (
    ThinQHumidifierEntityDescription(
        key="humidifier",
        icon="mdi:air-humidifier",
        name=None,
        device_class=HumidifierDeviceClass.HUMIDIFIER,
        translation_key="translation_humidifier",
        property_info=PropertyInfo(
            key="humidifier",
            mode=PropertyMode.FEATURED,
            children=(
                PropertyInfo(
                    key=Operation.HUMIDIFIER_OPERATION_MODE,
                    feature=PropertyFeature.POWER,
                ),
                PropertyInfo(
                    key=JobMode.CURRENT_JOB_MODE,
                    feature=PropertyFeature.OP_MODE,
                ),
                PropertyInfo(
                    key=Humidity.CURRENT_HUMIDITY,
                    feature=PropertyFeature.CURRENT_HUMIDITY,
                ),
                PropertyInfo(
                    key=Humidity.TARGET_HUMIDITY,
                    feature=PropertyFeature.TARGET_HUMIDITY,
                ),
            ),
        ),
    ),
)
HUMIDIFIER_NUMBER: tuple[ThinQNumberEntityDescription, ...] = (
    HUMIDITY_NUMBER_DESC[Humidity.TARGET_HUMIDITY],
    TIMER_NUMBER_DESC[Timer.SLEEP_TIMER_RELATIVE_HOUR_TO_STOP],
)
HUMIDIFIER_SELECT: tuple[ThinQSelectEntityDescription, ...] = (
    HUMIDITY_SELECT_DESC[Humidity.WARM_MODE],
    AIR_FLOW_SELECT_DESC[AirFlow.WIND_STRENGTH],
    DISPLAY_SELECT_DESC[Display.LIGHT],
    JOB_MODE_SELECT_DESC[JobMode.CURRENT_JOB_MODE],
    MOOD_LAMP_SELECT_DESC[MoodLamp.MOOD_LAMP_STATE],
    OPERATION_SELECT_DESC[Operation.AUTO_MODE],
    OPERATION_SELECT_DESC[Operation.SLEEP_MODE],
    OPERATION_SELECT_DESC[Operation.HYGIENE_DRY_MODE],
)
HUMIDIFIER_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    AIR_QUALITY_SENSOR_DESC[AirQuality.PM1],
    AIR_QUALITY_SENSOR_DESC[AirQuality.PM2],
    AIR_QUALITY_SENSOR_DESC[AirQuality.PM10],
    AIR_QUALITY_SENSOR_DESC[AirQuality.HUMIDITY],
    AIR_QUALITY_SENSOR_DESC[AirQuality.TEMPERATURE],
    AIR_QUALITY_SENSOR_DESC[AirQuality.TOTAL_POLLUTION],
    AIR_QUALITY_SENSOR_DESC[AirQuality.MONITORING_ENABLED],
    COMMON_SENSOR_DESC[Common.NOTIFICATION],
    TIMER_SENSOR_DESC[Timer.ABSOLUTE_TO_START],
    TIMER_SENSOR_DESC[Timer.ABSOLUTE_TO_STOP],
    TIMER_SENSOR_DESC[Timer.SLEEP_TIMER_RELATIVE_TO_STOP],
)
HUMIDIFIER_SWITCH: tuple[ThinQSwitchEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[Operation.HUMIDIFIER_OPERATION_MODE],
)
HUMIDIFIER_TEXT: tuple[ThinQTextEntityDescription, ...] = (
    TIMER_TEXT_DESC[Timer.ABSOLUTE_TO_START],
    TIMER_TEXT_DESC[Timer.ABSOLUTE_TO_STOP],
)
# KIMCHI_REFRIGERATOR Description
KIMCHI_REFRIGERATOR_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    COMMON_SENSOR_DESC[Common.NOTIFICATION],
    REFRIGERATION_SENSOR_DESC[Refrigeration.FRESH_AIR_FILTER],
    REFRIGERATION_SENSOR_DESC[Refrigeration.ONE_TOUCH_FILTER],
    TEMPERATURE_SENSOR_DESC[Temperature.TARGET_TEMPERATURE],
)

# MICROWAVE_OVEN Description
MICROWAVE_OVEN_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    COMMON_SENSOR_DESC[Common.NOTIFICATION],
    RUN_STATE_SENSOR_DESC[RunState.CURRENT_STATE],
    TIMER_SENSOR_DESC[Timer.REMAIN_MS],
)
MICROWAVE_OVEN_NUMBER: tuple[ThinQNumberEntityDescription, ...] = (
    LAMP_NUMBER_DESC[Lamp.LAMP_BRIGHTNESS],
    VENTILATION_NUMBER_DESC[Ventilation.FAN_SPEED],
)

# OVEN Description
OVEN_NUMBER: tuple[ThinQNumberEntityDescription, ...] = (
    TEMPERATURE_NUMBER_DESC[Temperature.TARGET_TEMPERATURE],
)
OVEN_SELECT: tuple[ThinQSelectEntityDescription, ...] = (
    COOK_SELECT_DESC[Cook.COOK_MODE],
    OPERATION_SELECT_DESC[Operation.OVEN_OPERATION_MODE],
)
OVEN_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    COMMON_SENSOR_DESC[Common.NOTIFICATION],
    RUN_STATE_SENSOR_DESC[RunState.CURRENT_STATE],
    TEMPERATURE_SENSOR_DESC[Temperature.TARGET_TEMPERATURE],
    TIMER_SENSOR_DESC[Timer.REMAIN],
    TIMER_SENSOR_DESC[Timer.TARGET],
)
OVEN_TIME: tuple[ThinQTimeEntityDescription, ...] = (
    TIMER_TIME_DESC[Timer.TARGET],
    TIMER_TIME_DESC[Timer.TIMER],
)

# PLANT_CULTIVATOR Description
PLANT_CULTIVATOR_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    LIGHT_SENSOR_DESC[Light.BRIGHTNESS],
    LIGHT_SENSOR_DESC[Light.DURATION],
    LIGHT_SENSOR_DESC[Light.START_TIME],
    LIGHT_SENSOR_DESC[Light.END_TIME],
    RUN_STATE_SENSOR_DESC[RunState.CURRENT_STATE],
    RUN_STATE_SENSOR_DESC[RunState.GROWTH_MODE],
    RUN_STATE_SENSOR_DESC[RunState.WIND_VOLUME],
    TEMPERATURE_SENSOR_DESC[Temperature.DAY_TARGET_TEMPERATURE],
    TEMPERATURE_SENSOR_DESC[Temperature.NIGHT_TARGET_TEMPERATURE],
    TEMPERATURE_SENSOR_DESC[Temperature.TEMPERATURE_STATE],
)

# REFRIGERATOR Description
REFRIGERATOR_BINARY_SENSOR: tuple[ThinQBinarySensorEntityDescription, ...] = (
    ECO_FRIENDLY_BINARY_SENSOR_DESC[EcoFriendly.ECO_FRIENDLY_MODE],
    POWER_SAVE_BINARY_SENSOR_DESC[PowerSave.POWER_SAVE_ENABLED],
    SABBATH_BINARY_SENSOR_DESC[Sabbath.SABBATH_MODE],
)
REFRIGERATOR_SELECT: tuple[ThinQSelectEntityDescription, ...] = (
    REFRIGERATION_SELECT_DESC[Refrigeration.EXPRESS_MODE],
    REFRIGERATION_SELECT_DESC[Refrigeration.RAPID_FREEZE],
    REFRIGERATION_SELECT_DESC[Refrigeration.FRESH_AIR_FILTER],
)
REFRIGERATOR_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    COMMON_SENSOR_DESC[Common.NOTIFICATION],
    DOOR_STATUS_SENSOR_DESC[DoorStatus.DOOR_STATE],
    REFRIGERATION_SENSOR_DESC[Refrigeration.FRESH_AIR_FILTER],
    WATER_FILTER_INFO_SENSOR_DESC[WaterFilterInfo.USED_TIME],
)
REFRIGERATOR_NUMBER: tuple[ThinQNumberEntityDescription, ...] = (
    TEMPERATURE_NUMBER_DESC[Temperature.TARGET_TEMPERATURE],
)

# ROBOT_CLEANER Description
ROBOT_CLEANER_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    COMMON_SENSOR_DESC[Common.ERROR],
    COMMON_SENSOR_DESC[Common.NOTIFICATION],
    RUN_STATE_SENSOR_DESC[RunState.CURRENT_STATE],
    JOB_MODE_SENSOR_DESC[JobMode.CURRENT_JOB_MODE],
    # TIMER_SENSOR_DESC[Timer.ABSOLUTE_TO_START],
    TIMER_SENSOR_DESC[Timer.RUNNING],
)
ROBOT_CLEANER_TIME: tuple[ThinQTimeEntityDescription, ...] = (
    TIMER_TIME_DESC[Timer.ABSOLUTE_TO_START],
)
ROBOT_CLEANER_TEXT: tuple[ThinQTextEntityDescription, ...] = (
    TIMER_TEXT_DESC[Timer.ABSOLUTE_TO_START],
)
ROBOT_CLEANER_VACUUM: tuple[ThinQStateVacuumEntityDescription, ...] = (
    ThinQStateVacuumEntityDescription(
        key="vacuum",
        icon="mdi:robot-vacuum",
        name=None,
        translation_key="translation_vacuum",
        property_info=PropertyInfo(
            key="robot_vacuum",
            mode=PropertyMode.FEATURED,
            children=(
                PropertyInfo(
                    key=Operation.CLEAN_OPERATION_MODE,
                    feature=PropertyFeature.POWER,
                ),
                PropertyInfo(
                    key=Battery.LEVEL,
                    mode=PropertyMode.SELECTIVE,
                    feature=PropertyFeature.BATTERY,
                    children=(PropertyInfo(key=Battery.PERCENT),),
                ),
                PropertyInfo(
                    key=RunState.CURRENT_STATE, feature=PropertyFeature.STATE
                ),
            ),
        ),
    ),
)

# STICK_CLEANER Description
STICK_CLEANER_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    COMMON_SENSOR_DESC[Common.NOTIFICATION],
    BATTERY_SENSOR_DESC[Battery.LEVEL],
    JOB_MODE_SENSOR_DESC[JobMode.CURRENT_JOB_MODE],
    RUN_STATE_SENSOR_DESC[RunState.CURRENT_STATE],
)

# STYLER Description
STYLER_NUMBER: tuple[ThinQNumberEntityDescription, ...] = (
    TIMER_NUMBER_DESC[Timer.RELATIVE_HOUR_TO_STOP_WM],
)
STYLER_SELECT: tuple[ThinQSelectEntityDescription, ...] = (
    OPERATION_SELECT_DESC[Operation.STYLER_OPERATION_MODE],
    # ToDo: When we should support combined property?
    # COURSE_SELECT_DESC[Course.STYLING_COURSE],
)
STYLER_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    COMMON_SENSOR_DESC[Common.ERROR],
    COMMON_SENSOR_DESC[Common.NOTIFICATION],
    RUN_STATE_SENSOR_DESC[RunState.CURRENT_STATE],
    TIMER_SENSOR_DESC[Timer.REMAIN_HM],
    TIMER_SENSOR_DESC[Timer.RELATIVE_TO_STOP_WM],
    TIMER_SENSOR_DESC[Timer.TOTAL],
)

# SYSTEM_BOILER Description
SYSTEM_BOILER_CLIMATE: tuple[ThinQClimateEntityDescription, ...] = (
    ThinQClimateEntityDescription(
        key="climate",
        icon="mdi:water-boiler-auto",
        name=None,
        translation_key="translation_climate",
        property_info=PropertyInfo(
            key="system_boiler_climate",
            mode=PropertyMode.FEATURED,
            children=(
                PropertyInfo(
                    key=Operation.BOILER_OPERATION_MODE,
                    feature=PropertyFeature.POWER,
                ),
                PropertyInfo(
                    key=Temperature.CURRENT_TEMPERATURE,
                    feature=PropertyFeature.CURRENT_TEMP,
                    unit_info=PropertyInfo(key=Temperature.UNIT),
                ),
                PropertyInfo(
                    key=Temperature.TARGET_TEMPERATURE,
                    feature=PropertyFeature.TARGET_TEMP,
                    unit_info=PropertyInfo(key=Temperature.UNIT),
                    alt_range={"max": 30, "min": 16, "step": 1},
                ),
                PropertyInfo(
                    key=Temperature.COOL_TARGET_TEMPERATURE,
                    feature=PropertyFeature.COOL_TARGET_TEMP,
                    unit_info=PropertyInfo(key=Temperature.UNIT),
                ),
                PropertyInfo(
                    key=Temperature.HEAT_TARGET_TEMPERATURE,
                    feature=PropertyFeature.HEAT_TARGET_TEMP,
                    unit_info=PropertyInfo(key=Temperature.UNIT),
                ),
                PropertyInfo(
                    key=JobMode.CURRENT_JOB_MODE,
                    feature=PropertyFeature.HVAC_MODE,
                ),
            ),
        ),
    ),
)
SYSTEM_BOILER_SELECT: tuple[ThinQSelectEntityDescription, ...] = (
    OPERATION_SELECT_DESC[Operation.HOT_WATER_MODE],
)
SYSTEM_BOILER_SWITCH: tuple[ThinQSwitchEntityDescription, ...] = (
    OPERATION_SWITCH_DESC[Operation.BOILER_OPERATION_MODE],
)

# WASHER Description
WASHER_NUMBER: tuple[ThinQNumberEntityDescription, ...] = (
    TIMER_NUMBER_DESC[Timer.RELATIVE_HOUR_TO_START_WM],
    TIMER_NUMBER_DESC[Timer.RELATIVE_HOUR_TO_STOP_WM],
)
WASHER_SELECT: tuple[ThinQSelectEntityDescription, ...] = (
    OPERATION_SELECT_DESC[Operation.WASHER_OPERATION_MODE],
)
WASHER_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    COMMON_SENSOR_DESC[Common.ERROR],
    COMMON_SENSOR_DESC[Common.NOTIFICATION],
    # DETERGENT_SENSOR_DESC[Detergent.DETERGENT_SETTING],  # not used
    RUN_STATE_SENSOR_DESC[RunState.CURRENT_STATE],
    TIMER_SENSOR_DESC[Timer.RELATIVE_TO_START],
    TIMER_SENSOR_DESC[Timer.RELATIVE_TO_STOP_WM],
    TIMER_SENSOR_DESC[Timer.REMAIN_HM],
    TIMER_SENSOR_DESC[Timer.TOTAL],
)

# WASHTOWER Description
WASHTOWER_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    COMMON_SENSOR_DESC[Common.ERROR],
    COMMON_SENSOR_DESC[Common.NOTIFICATION],
    # DETERGENT_SENSOR_DESC[Detergent.DETERGENT_SETTING],  # not used
    RUN_STATE_SENSOR_DESC[RunState.CURRENT_STATE],
    TIMER_SENSOR_DESC[Timer.RELATIVE_TO_START],
    TIMER_SENSOR_DESC[Timer.RELATIVE_TO_STOP_WM],
    TIMER_SENSOR_DESC[Timer.REMAIN_HM],
    TIMER_SENSOR_DESC[Timer.TOTAL],
)
WASHTOWER_SELECT: tuple[ThinQSelectEntityDescription, ...] = (
    OPERATION_SELECT_DESC[Operation.DRYER_OPERATION_MODE],
    OPERATION_SELECT_DESC[Operation.WASHER_OPERATION_MODE],
)

# WATER_HEATER Description
WATER_HEATER_NUMBER: tuple[ThinQNumberEntityDescription, ...] = (
    TEMPERATURE_NUMBER_DESC[Temperature.TARGET_TEMPERATURE],
)
WATER_HEATER_SELECT: tuple[ThinQSelectEntityDescription, ...] = (
    JOB_MODE_SELECT_DESC[JobMode.CURRENT_JOB_MODE],
)
WATER_HEATER_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    TEMPERATURE_SENSOR_DESC[Temperature.CURRENT_TEMPERATURE],
    OPERATION_SENSOR_DESC[Operation.WATER_HEATER_OPERATION_MODE],
)
WATER_HEATER_WATER_HEATER: tuple[
    ThinQWaterHeaterEntityEntityDescription, ...
] = (
    ThinQWaterHeaterEntityEntityDescription(
        key="water_heater",
        icon="mdi:water-boiler",
        name=None,
        translation_key="translation_water_heater",
        property_info=PropertyInfo(
            key="water_heater",
            mode=PropertyMode.FEATURED,
            children=(
                PropertyInfo(
                    key=Operation.WATER_HEATER_OPERATION_MODE,
                    feature=PropertyFeature.POWER,
                ),
                PropertyInfo(
                    key=Temperature.CURRENT_TEMPERATURE,
                    feature=PropertyFeature.CURRENT_TEMP,
                    unit_info=PropertyInfo(key=Temperature.UNIT),
                ),
                PropertyInfo(
                    key=Temperature.TARGET_TEMPERATURE,
                    feature=PropertyFeature.TARGET_TEMP,
                    unit_info=PropertyInfo(key=Temperature.UNIT),
                ),
                PropertyInfo(
                    key=JobMode.CURRENT_JOB_MODE,
                    feature=PropertyFeature.OP_MODE,
                ),
            ),
        ),
    ),
)

# WATER_PURIFIER Description
WATER_PURIFIER_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    RUN_STATE_SENSOR_DESC[RunState.COCK_STATE],
    RUN_STATE_SENSOR_DESC[RunState.STERILIZING_STATE],
    WATER_INFO_SENSOR_DESC[WaterInfo.WATER_TYPE],
)

# WINE_CELLAR Description
WINE_CELLAR_BINARY_SENSOR: tuple[ThinQBinarySensorEntityDescription, ...] = (
    SABBATH_BINARY_SENSOR_DESC[Sabbath.SABBATH_MODE],
)
WINE_CELLAR_NUMBER: tuple[ThinQNumberEntityDescription, ...] = (
    OPERATION_NUMBER_DESC[Operation.LIGHT_STATUS],
    TEMPERATURE_NUMBER_DESC[Temperature.TARGET_TEMPERATURE],
)
WINE_CELLAR_SELECT: tuple[ThinQSelectEntityDescription, ...] = (
    OPERATION_SELECT_DESC[Operation.LIGHT_BRIGHTNESS],
    OPERATION_SELECT_DESC[Operation.OPTIMAL_HUMIDITY],
)
WINE_CELLAR_SENSOR: tuple[ThinQSensorEntityDescription, ...] = (
    COMMON_SENSOR_DESC[Common.NOTIFICATION],
)

# The entity escription map for each device type.
ENTITY_MAP = {
    DeviceType.AIR_CONDITIONER: {
        Platform.CLIMATE: AIRCONDITIONER_CLIMATE,
        Platform.EVENT: NOTIFICATION_EVENT,
        Platform.NUMBER: AIRCONDITIONER_NUMBER,
        Platform.SELECT: AIRCONDITIONER_SELECT,
        Platform.SENSOR: AIRCONDITIONER_SENSOR,
        Platform.TEXT: AIRCONDITIONER_TEXT,
        # Platform.TIME: ABSOLUTE_TIMER_TIME,  # not used limitation
    },
    DeviceType.AIR_PURIFIER_FAN: {
        Platform.EVENT: NOTIFICATION_EVENT,
        Platform.NUMBER: AIR_PURIFIER_FAN_NUMBER,
        Platform.SELECT: AIR_PURIFIER_FAN_SELECT,
        Platform.SENSOR: AIR_PURIFIER_FAN_SENSOR,
        Platform.SWITCH: AIR_PURIFIER_FAN_SWITCH,
        Platform.TEXT: AIR_PURIFIER_FAN_TEXT,
        # Platform.TIME: ABSOLUTE_TIMER_TIME, # not used limitation
    },
    DeviceType.AIR_PURIFIER: {
        Platform.EVENT: NOTIFICATION_EVENT,
        Platform.SELECT: AIRPURIFIER_SELECT,
        Platform.SENSOR: AIRPURIFIER_SENSOR,
        Platform.SWITCH: AIRPURIFIER_SWITCH,
        Platform.TEXT: AIRPURIFIER_TEXT,
        # Platform.TIME: ABSOLUTE_TIMER_TIME, # not used limitation
    },
    DeviceType.CEILING_FAN: {
        Platform.FAN: CEILING_FAN_FAN,
    },
    DeviceType.COOKTOP: {
        Platform.BINARY_SENSOR: REMOTE_CONTROL_BINARY_SENSOR,
        Platform.BUTTON: COOKTOP_BUTTON,
        # Platform.NUMBER: COOKTOP_NUMBER, # not used limitation
        Platform.SENSOR: COOKTOP_SENSOR,
    },
    DeviceType.DEHUMIDIFIER: {
        Platform.EVENT: NOTIFICATION_EVENT,
        Platform.HUMIDIFIER: DEHUMIDIFIER_HUMIDIFIER,
        Platform.SELECT: DEHUMIDIFIER_SELECT,
        Platform.SENSOR: DEHUMIDIFIER_SENSOR,
        Platform.SWITCH: DEHUMIDIFIER_SWITCH,
    },
    DeviceType.DISH_WASHER: {
        Platform.BINARY_SENSOR: DISH_WASHER_BINARY_SENSOR,
        Platform.EVENT: NOTIFICATION_EVENT,
        Platform.SELECT: DISH_WASHER_SELECT,
        Platform.SENSOR: DISH_WASHER_SENSOR,
    },
    DeviceType.DRYER: {
        Platform.BINARY_SENSOR: REMOTE_CONTROL_BINARY_SENSOR,
        Platform.EVENT: NOTIFICATION_EVENT,
        Platform.NUMBER: DRYER_NUMBER,
        Platform.SELECT: DRYER_SELECT,
        Platform.SENSOR: DRYER_SENSOR,
    },
    DeviceType.HOME_BREW: {
        Platform.SENSOR: HOME_BREW_SENSOR,
    },
    DeviceType.HOOD: {
        Platform.NUMBER: HOOD_NUMBER,
        Platform.SENSOR: HOOD_SENSOR,
    },
    DeviceType.HUMIDIFIER: {
        # Humidifier platform is not currently supported because there
        # is no temperature step feature.
        # Platform.HUMIDIFIER: HUMIDIFIER_HUMIDIFIER,
        Platform.EVENT: NOTIFICATION_EVENT,
        Platform.NUMBER: HUMIDIFIER_NUMBER,
        Platform.SELECT: HUMIDIFIER_SELECT,
        Platform.SENSOR: HUMIDIFIER_SENSOR,
        Platform.SWITCH: HUMIDIFIER_SWITCH,
        Platform.TEXT: HUMIDIFIER_TEXT,
        # Platform.TIME: ABSOLUTE_TIMER_TIME,
    },
    DeviceType.KIMCHI_REFRIGERATOR: {
        Platform.EVENT: NOTIFICATION_EVENT,
        Platform.SENSOR: KIMCHI_REFRIGERATOR_SENSOR,
    },
    DeviceType.MICROWAVE_OVEN: {
        Platform.EVENT: NOTIFICATION_EVENT,
        Platform.NUMBER: MICROWAVE_OVEN_NUMBER,
        Platform.SENSOR: MICROWAVE_OVEN_SENSOR,
    },
    DeviceType.OVEN: {
        Platform.BINARY_SENSOR: REMOTE_CONTROL_BINARY_SENSOR,
        Platform.EVENT: NOTIFICATION_EVENT,
        Platform.NUMBER: OVEN_NUMBER,
        Platform.SELECT: OVEN_SELECT,
        Platform.SENSOR: OVEN_SENSOR,
        # Platform.TIME: OVEN_TIME, # not used limitation
    },
    DeviceType.PLANT_CULTIVATOR: {
        Platform.SENSOR: PLANT_CULTIVATOR_SENSOR,
    },
    DeviceType.REFRIGERATOR: {
        Platform.BINARY_SENSOR: REFRIGERATOR_BINARY_SENSOR,
        Platform.EVENT: NOTIFICATION_EVENT,
        Platform.NUMBER: REFRIGERATOR_NUMBER,
        Platform.SELECT: REFRIGERATOR_SELECT,
        Platform.SENSOR: REFRIGERATOR_SENSOR,
    },
    DeviceType.ROBOT_CLEANER: {
        Platform.EVENT: NOTIFICATION_EVENT,
        Platform.SENSOR: ROBOT_CLEANER_SENSOR,
        Platform.TEXT: ROBOT_CLEANER_TEXT,
        # Platform.TIME: ROBOT_CLEANER_TIME, # not used limitation
        Platform.VACUUM: ROBOT_CLEANER_VACUUM,
    },
    DeviceType.STICK_CLEANER: {
        Platform.EVENT: NOTIFICATION_EVENT,
        Platform.SENSOR: STICK_CLEANER_SENSOR,
    },
    DeviceType.STYLER: {
        Platform.BINARY_SENSOR: REMOTE_CONTROL_BINARY_SENSOR,
        Platform.EVENT: NOTIFICATION_EVENT,
        Platform.NUMBER: STYLER_NUMBER,
        Platform.SELECT: STYLER_SELECT,
        Platform.SENSOR: STYLER_SENSOR,
    },
    DeviceType.SYSTEM_BOILER: {
        Platform.CLIMATE: SYSTEM_BOILER_CLIMATE,
        Platform.SELECT: SYSTEM_BOILER_SELECT,
        # Platform.SWITCH: SYSTEM_BOILER_SWITCH,  # turn on by hvac's button
    },
    DeviceType.WASHCOMBO_MAIN: {
        Platform.BINARY_SENSOR: REMOTE_CONTROL_BINARY_SENSOR,
        Platform.NUMBER: WASHER_NUMBER,
        Platform.SELECT: WASHER_SELECT,
        Platform.SENSOR: WASHER_SENSOR,
    },
    DeviceType.WASHCOMBO_MINI: {
        Platform.BINARY_SENSOR: REMOTE_CONTROL_BINARY_SENSOR,
        Platform.NUMBER: WASHER_NUMBER,
        Platform.SELECT: WASHER_SELECT,
        Platform.SENSOR: WASHER_SENSOR,
    },
    DeviceType.WASHER: {
        Platform.BINARY_SENSOR: REMOTE_CONTROL_BINARY_SENSOR,
        Platform.EVENT: NOTIFICATION_EVENT,
        Platform.NUMBER: WASHER_NUMBER,
        Platform.SELECT: WASHER_SELECT,
        Platform.SENSOR: WASHER_SENSOR,
    },
    DeviceType.WASHTOWER_DRYER: {
        Platform.BINARY_SENSOR: REMOTE_CONTROL_BINARY_SENSOR,
        Platform.NUMBER: DRYER_NUMBER,
        Platform.SELECT: DRYER_SELECT,
        Platform.SENSOR: DRYER_SENSOR,
    },
    DeviceType.WASHTOWER: {
        Platform.BINARY_SENSOR: REMOTE_CONTROL_BINARY_SENSOR,
        Platform.EVENT: NOTIFICATION_EVENT,
        Platform.NUMBER: WASHER_NUMBER,
        Platform.SELECT: WASHTOWER_SELECT,
        Platform.SENSOR: WASHTOWER_SENSOR,
    },
    DeviceType.WASHTOWER_WASHER: {
        Platform.BINARY_SENSOR: REMOTE_CONTROL_BINARY_SENSOR,
        Platform.NUMBER: WASHER_NUMBER,
        Platform.SELECT: WASHER_SELECT,
        Platform.SENSOR: WASHER_SENSOR,
    },
    DeviceType.WATER_HEATER: {
        Platform.NUMBER: WATER_HEATER_NUMBER,
        Platform.SELECT: WATER_HEATER_SELECT,
        Platform.SENSOR: WATER_HEATER_SENSOR,
        # Platform.WATER_HEATER: WATER_HEATER_WATER_HEATER,
        # Water_heater platform is not currently supported because there
        # is no temperature step feature. frontend's default step is 0.5
    },
    DeviceType.WATER_PURIFIER: {
        Platform.SENSOR: WATER_PURIFIER_SENSOR,
    },
    DeviceType.WINE_CELLAR: {
        Platform.BINARY_SENSOR: WINE_CELLAR_BINARY_SENSOR,
        Platform.EVENT: NOTIFICATION_EVENT,
        Platform.NUMBER: WINE_CELLAR_NUMBER,
        Platform.SELECT: WINE_CELLAR_SELECT,
        Platform.SENSOR: WINE_CELLAR_SENSOR,
    },
}

UNIT_CONVERSION_MAP: dict[str, str] = {
    "F": UnitOfTemperature.FAHRENHEIT,
    "C": UnitOfTemperature.CELSIUS,
}


class ThinQEntity(CoordinatorEntity, Generic[ThinQEntityDescriptionT]):
    """The base implementation of all lg thinq entities."""

    target_platform: Platform | None
    entity_description: ThinQEntityDescriptionT

    def __init__(
        self,
        device: LGDevice,
        property: Property,
        entity_description: ThinQEntityDescriptionT,
    ) -> None:
        """Initialize an entity."""
        super().__init__(device.coordinator)

        self._device = device
        self._property = property
        self.entity_description = entity_description
        self._attr_device_info = device.device_info

        # If there exist a location, add the prefix location name.
        location: str | None = None
        if self.property is not None:
            location = self.property.location
            location_str = (
                ""
                if location is None
                or location == "main"
                or location == "oven"
                or (device.sub_id is not None and device.sub_id == location)
                else f"{location} "
            )
            self._attr_translation_placeholders = {"location": location_str}

        # Set the unique key.
        unique_key = (
            f"{entity_description.key}"
            if location is None
            else f"{location}_{entity_description.key}"
        )
        self._attr_unique_id = f"{device.unique_id}_{unique_key}"

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._device.is_connected

    @property
    def device(self) -> LGDevice:
        """Returns the connected device."""
        return self._device

    @property
    def property(self) -> Property:
        """Returns the property of entity."""
        return self._property

    def get_property(self, feature: PropertyFeature = None) -> Property | None:
        """Returns the property corresponding to the feature."""
        if feature is None:
            return self.property
        else:
            return self.property.get_featured_property(feature)

    def get_options(self, feature: PropertyFeature = None) -> list[str] | None:
        """Returns the property options of entity."""
        property = self.get_property(feature)
        return property.options if property is not None else None

    def get_range(self, feature: PropertyFeature = None) -> Range | None:
        """Returns the property range of entity."""
        property = self.get_property(feature)
        return property.range if property is not None else None

    def get_unit(self, feature: PropertyFeature = None) -> str | None:
        """Returns the property unit of entity."""
        property = self.get_property(feature)
        return property.unit if property is not None else None

    def get_value(self, feature: PropertyFeature = None) -> Any:
        """Returns the property value of entity."""
        property = self.get_property(feature)
        return property.get_value() if property is not None else None

    def get_value_as_bool(self, feature: PropertyFeature = None) -> bool:
        """Returns the property value of entity as bool."""
        property = self.get_property(feature)
        return property.get_value_as_bool() if property is not None else None

    async def async_post_value(
        self, value: Any, feature: PropertyFeature = None
    ) -> None:
        """Post the value of entity to server."""
        property = self.get_property(feature)
        if property is not None:
            await property.async_post_value(value)

    def _get_unit_of_measurement(self, unit: str, fallback: str) -> str:
        """Convert ThinQ unit string to HA unit string."""
        return UNIT_CONVERSION_MAP.get(unit, fallback)

    def _update_status(self) -> None:
        """
        Update status itself.
        All inherited classes can update their own status in here.
        """
        if self.entity_description.translation_key is None:
            location: str = self.property.location
            if location is not None:
                name: str = self.entity_description.name
                if name is not None:
                    self._attr_name = f"{location} {name}"
                else:
                    self._attr_name = f"{location} {self.property.key}"
            else:
                self._attr_name = self.property.key

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        self._update_status()
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        await super().async_added_to_hass()
        self._handle_coordinator_update()

    @classmethod
    def create_entities(cls, device_list: list[LGDevice]) -> list[ThinQEntity]:
        """Create entities with descriptions from the entity map."""
        if not device_list or cls.target_platform is None:
            return []

        _LOGGER.debug(
            "async_create_entities. cls=%s, target_platform=%s",
            cls.__name__,
            cls.target_platform,
        )

        entities: list[ThinQEntity] = []
        for device in device_list:
            # Get the entitiy description map for the device type.
            desc_map: dict[Platform, tuple] = ENTITY_MAP.get(device.type)
            if not desc_map:
                continue

            # Get entitiy descriptions for the target platform.
            desc_list: tuple[ThinQEntityDescriptionT] = desc_map.get(
                cls.target_platform
            )
            if not desc_list:
                continue

            # Try to create entities for all entity descriptions.
            for desc in desc_list:
                properties: list[Property] = create_properties(
                    device, desc.property_info, cls.target_platform
                )
                if not properties:
                    continue

                for property in properties:
                    entities.append(cls(device, property, desc))

                    _LOGGER.debug(
                        "[%s] Add %s entity for [%s]",
                        device.name,
                        cls.target_platform,
                        desc.key,
                    )

        return entities
