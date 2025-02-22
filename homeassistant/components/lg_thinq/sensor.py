"""Support for sensor entities."""

from __future__ import annotations

from datetime import datetime, time, timedelta
import logging

from thinqconnect import DeviceType
from thinqconnect.devices.const import Property as ThinQProperty
from thinqconnect.integration import ActiveMode, ThinQPropertyEx, TimerProperty

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import ThinqConfigEntry
from .coordinator import DeviceDataUpdateCoordinator
from .entity import ThinQEntity

AIR_QUALITY_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    ThinQProperty.PM1: SensorEntityDescription(
        key=ThinQProperty.PM1,
        device_class=SensorDeviceClass.PM1,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ThinQProperty.PM2: SensorEntityDescription(
        key=ThinQProperty.PM2,
        device_class=SensorDeviceClass.PM25,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ThinQProperty.PM10: SensorEntityDescription(
        key=ThinQProperty.PM10,
        device_class=SensorDeviceClass.PM10,
        native_unit_of_measurement=CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ThinQProperty.HUMIDITY: SensorEntityDescription(
        key=ThinQProperty.HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    ThinQProperty.MONITORING_ENABLED: SensorEntityDescription(
        key=ThinQProperty.MONITORING_ENABLED,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQProperty.MONITORING_ENABLED,
    ),
    ThinQProperty.TEMPERATURE: SensorEntityDescription(
        key=ThinQProperty.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=ThinQProperty.TEMPERATURE,
    ),
    ThinQProperty.ODOR_LEVEL: SensorEntityDescription(
        key=ThinQProperty.ODOR_LEVEL,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQProperty.ODOR_LEVEL,
    ),
    ThinQProperty.TOTAL_POLLUTION_LEVEL: SensorEntityDescription(
        key=ThinQProperty.TOTAL_POLLUTION_LEVEL,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQProperty.TOTAL_POLLUTION_LEVEL,
    ),
}
BATTERY_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    ThinQProperty.BATTERY_PERCENT: SensorEntityDescription(
        key=ThinQProperty.BATTERY_PERCENT,
        translation_key=ThinQProperty.BATTERY_LEVEL,
    ),
}
DISH_WASHING_COURSE_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    ThinQProperty.CURRENT_DISH_WASHING_COURSE: SensorEntityDescription(
        key=ThinQProperty.CURRENT_DISH_WASHING_COURSE,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQProperty.CURRENT_DISH_WASHING_COURSE,
    )
}
FILTER_INFO_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    ThinQProperty.FILTER_LIFETIME: SensorEntityDescription(
        key=ThinQProperty.FILTER_LIFETIME,
        native_unit_of_measurement=UnitOfTime.HOURS,
        translation_key=ThinQProperty.FILTER_LIFETIME,
    ),
    ThinQProperty.FILTER_REMAIN_PERCENT: SensorEntityDescription(
        key=ThinQProperty.FILTER_REMAIN_PERCENT,
        native_unit_of_measurement=PERCENTAGE,
        translation_key=ThinQProperty.FILTER_LIFETIME,
    ),
}
HUMIDITY_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    ThinQProperty.CURRENT_HUMIDITY: SensorEntityDescription(
        key=ThinQProperty.CURRENT_HUMIDITY,
        device_class=SensorDeviceClass.HUMIDITY,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
    )
}
JOB_MODE_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    ThinQProperty.CURRENT_JOB_MODE: SensorEntityDescription(
        key=ThinQProperty.CURRENT_JOB_MODE,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQProperty.CURRENT_JOB_MODE,
    ),
    ThinQPropertyEx.CURRENT_JOB_MODE_STICK_CLEANER: SensorEntityDescription(
        key=ThinQProperty.CURRENT_JOB_MODE,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQPropertyEx.CURRENT_JOB_MODE_STICK_CLEANER,
    ),
    ThinQProperty.PERSONALIZATION_MODE: SensorEntityDescription(
        key=ThinQProperty.PERSONALIZATION_MODE,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQProperty.PERSONALIZATION_MODE,
    ),
}
LIGHT_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    ThinQProperty.BRIGHTNESS: SensorEntityDescription(
        key=ThinQProperty.BRIGHTNESS,
        translation_key=ThinQProperty.BRIGHTNESS,
    ),
    ThinQProperty.DURATION: SensorEntityDescription(
        key=ThinQProperty.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        translation_key=ThinQProperty.DURATION,
    ),
}
POWER_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    ThinQProperty.POWER_LEVEL: SensorEntityDescription(
        key=ThinQProperty.POWER_LEVEL,
        translation_key=ThinQProperty.POWER_LEVEL,
    )
}
PREFERENCE_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    ThinQProperty.RINSE_LEVEL: SensorEntityDescription(
        key=ThinQProperty.RINSE_LEVEL,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQProperty.RINSE_LEVEL,
    ),
    ThinQProperty.SOFTENING_LEVEL: SensorEntityDescription(
        key=ThinQProperty.SOFTENING_LEVEL,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQProperty.SOFTENING_LEVEL,
    ),
}
RECIPE_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    ThinQProperty.RECIPE_NAME: SensorEntityDescription(
        key=ThinQProperty.RECIPE_NAME,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQProperty.RECIPE_NAME,
    ),
    ThinQProperty.WORT_INFO: SensorEntityDescription(
        key=ThinQProperty.WORT_INFO,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQProperty.WORT_INFO,
    ),
    ThinQProperty.YEAST_INFO: SensorEntityDescription(
        key=ThinQProperty.YEAST_INFO,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQProperty.YEAST_INFO,
    ),
    ThinQProperty.HOP_OIL_INFO: SensorEntityDescription(
        key=ThinQProperty.HOP_OIL_INFO,
        translation_key=ThinQProperty.HOP_OIL_INFO,
    ),
    ThinQProperty.FLAVOR_INFO: SensorEntityDescription(
        key=ThinQProperty.FLAVOR_INFO,
        translation_key=ThinQProperty.FLAVOR_INFO,
    ),
    ThinQProperty.BEER_REMAIN: SensorEntityDescription(
        key=ThinQProperty.BEER_REMAIN,
        native_unit_of_measurement=PERCENTAGE,
        translation_key=ThinQProperty.BEER_REMAIN,
    ),
}
REFRIGERATION_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    ThinQProperty.FRESH_AIR_FILTER: SensorEntityDescription(
        key=ThinQProperty.FRESH_AIR_FILTER,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQProperty.FRESH_AIR_FILTER,
    ),
}
RUN_STATE_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    ThinQProperty.CURRENT_STATE: SensorEntityDescription(
        key=ThinQProperty.CURRENT_STATE,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQProperty.CURRENT_STATE,
    ),
    ThinQProperty.COCK_STATE: SensorEntityDescription(
        key=ThinQProperty.COCK_STATE,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQProperty.COCK_STATE,
    ),
    ThinQProperty.STERILIZING_STATE: SensorEntityDescription(
        key=ThinQProperty.STERILIZING_STATE,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQProperty.STERILIZING_STATE,
    ),
    ThinQProperty.GROWTH_MODE: SensorEntityDescription(
        key=ThinQProperty.GROWTH_MODE,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQProperty.GROWTH_MODE,
    ),
    ThinQProperty.WIND_VOLUME: SensorEntityDescription(
        key=ThinQProperty.WIND_VOLUME,
        device_class=SensorDeviceClass.WIND_SPEED,
        translation_key=ThinQProperty.WIND_VOLUME,
    ),
}
TEMPERATURE_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    ThinQProperty.TARGET_TEMPERATURE: SensorEntityDescription(
        key=ThinQProperty.TARGET_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key=ThinQProperty.TARGET_TEMPERATURE,
    ),
    ThinQProperty.DAY_TARGET_TEMPERATURE: SensorEntityDescription(
        key=ThinQProperty.DAY_TARGET_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=ThinQProperty.DAY_TARGET_TEMPERATURE,
    ),
    ThinQProperty.NIGHT_TARGET_TEMPERATURE: SensorEntityDescription(
        key=ThinQProperty.NIGHT_TARGET_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=ThinQProperty.NIGHT_TARGET_TEMPERATURE,
    ),
    ThinQProperty.TEMPERATURE_STATE: SensorEntityDescription(
        key=ThinQProperty.TEMPERATURE_STATE,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQProperty.TEMPERATURE_STATE,
    ),
    ThinQProperty.CURRENT_TEMPERATURE: SensorEntityDescription(
        key=ThinQProperty.CURRENT_TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=ThinQProperty.CURRENT_TEMPERATURE,
    ),
    ThinQPropertyEx.ROOM_AIR_CURRENT_TEMPERATURE: SensorEntityDescription(
        key=ThinQPropertyEx.ROOM_AIR_CURRENT_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=ThinQPropertyEx.ROOM_AIR_CURRENT_TEMPERATURE,
    ),
    ThinQPropertyEx.ROOM_IN_WATER_CURRENT_TEMPERATURE: SensorEntityDescription(
        key=ThinQPropertyEx.ROOM_IN_WATER_CURRENT_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=ThinQPropertyEx.ROOM_IN_WATER_CURRENT_TEMPERATURE,
    ),
    ThinQPropertyEx.ROOM_OUT_WATER_CURRENT_TEMPERATURE: SensorEntityDescription(
        key=ThinQPropertyEx.ROOM_OUT_WATER_CURRENT_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=ThinQPropertyEx.ROOM_OUT_WATER_CURRENT_TEMPERATURE,
    ),
}
WATER_FILTER_INFO_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    ThinQProperty.USED_TIME: SensorEntityDescription(
        key=ThinQProperty.USED_TIME,
        native_unit_of_measurement=UnitOfTime.MONTHS,
        translation_key=ThinQProperty.USED_TIME,
    ),
}
WATER_INFO_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    ThinQProperty.WATER_TYPE: SensorEntityDescription(
        key=ThinQProperty.WATER_TYPE,
        translation_key=ThinQProperty.WATER_TYPE,
    ),
}
ELAPSED_DAY_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    ThinQProperty.ELAPSED_DAY_STATE: SensorEntityDescription(
        key=ThinQProperty.ELAPSED_DAY_STATE,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        translation_key=ThinQProperty.ELAPSED_DAY_STATE,
    ),
    ThinQProperty.ELAPSED_DAY_TOTAL: SensorEntityDescription(
        key=ThinQProperty.ELAPSED_DAY_TOTAL,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.DAYS,
        translation_key=ThinQProperty.ELAPSED_DAY_TOTAL,
    ),
}
TIME_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    TimerProperty.LIGHT_START: SensorEntityDescription(
        key=TimerProperty.LIGHT_START,
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key=TimerProperty.LIGHT_START,
    ),
    TimerProperty.ABSOLUTE_TO_START: SensorEntityDescription(
        key=TimerProperty.ABSOLUTE_TO_START,
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key=TimerProperty.ABSOLUTE_TO_START,
    ),
    TimerProperty.ABSOLUTE_TO_STOP: SensorEntityDescription(
        key=TimerProperty.ABSOLUTE_TO_STOP,
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key=TimerProperty.ABSOLUTE_TO_STOP,
    ),
}
TIMER_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    TimerProperty.TOTAL: SensorEntityDescription(
        key=TimerProperty.TOTAL,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        translation_key=TimerProperty.TOTAL,
    ),
    TimerProperty.RELATIVE_TO_START: SensorEntityDescription(
        key=TimerProperty.RELATIVE_TO_START,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        translation_key=TimerProperty.RELATIVE_TO_START,
    ),
    TimerProperty.RELATIVE_TO_STOP: SensorEntityDescription(
        key=TimerProperty.RELATIVE_TO_STOP,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        translation_key=TimerProperty.RELATIVE_TO_STOP,
    ),
    TimerProperty.SLEEP_TIMER_RELATIVE_TO_STOP: SensorEntityDescription(
        key=TimerProperty.SLEEP_TIMER_RELATIVE_TO_STOP,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        translation_key=TimerProperty.SLEEP_TIMER_RELATIVE_TO_STOP,
    ),
    TimerProperty.RELATIVE_TO_START_WM: SensorEntityDescription(
        key=TimerProperty.RELATIVE_TO_START,
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key=TimerProperty.RELATIVE_TO_START_WM,
    ),
    TimerProperty.RELATIVE_TO_STOP_WM: SensorEntityDescription(
        key=TimerProperty.RELATIVE_TO_STOP,
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key=TimerProperty.RELATIVE_TO_STOP_WM,
    ),
    TimerProperty.REMAIN: SensorEntityDescription(
        key=TimerProperty.REMAIN,
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key=TimerProperty.REMAIN,
    ),
    TimerProperty.RUNNING: SensorEntityDescription(
        key=TimerProperty.RUNNING,
        device_class=SensorDeviceClass.TIMESTAMP,
        translation_key=TimerProperty.RUNNING,
    ),
}

WASHER_SENSORS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=ThinQProperty.CYCLE_COUNT,
        translation_key=ThinQProperty.CYCLE_COUNT,
    ),
    RUN_STATE_SENSOR_DESC[ThinQProperty.CURRENT_STATE],
    TIMER_SENSOR_DESC[TimerProperty.TOTAL],
    TIMER_SENSOR_DESC[TimerProperty.RELATIVE_TO_START_WM],
    TIMER_SENSOR_DESC[TimerProperty.RELATIVE_TO_STOP_WM],
    TIMER_SENSOR_DESC[TimerProperty.REMAIN],
)
DEVICE_TYPE_SENSOR_MAP: dict[DeviceType, tuple[SensorEntityDescription, ...]] = {
    DeviceType.AIR_CONDITIONER: (
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM1],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM2],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM10],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.HUMIDITY],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.ODOR_LEVEL],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.TOTAL_POLLUTION_LEVEL],
        FILTER_INFO_SENSOR_DESC[ThinQProperty.FILTER_LIFETIME],
        FILTER_INFO_SENSOR_DESC[ThinQProperty.FILTER_REMAIN_PERCENT],
        TIMER_SENSOR_DESC[TimerProperty.RELATIVE_TO_START],
        TIMER_SENSOR_DESC[TimerProperty.RELATIVE_TO_STOP],
        TIMER_SENSOR_DESC[TimerProperty.SLEEP_TIMER_RELATIVE_TO_STOP],
        TIME_SENSOR_DESC[TimerProperty.ABSOLUTE_TO_START],
        TIME_SENSOR_DESC[TimerProperty.ABSOLUTE_TO_STOP],
    ),
    DeviceType.AIR_PURIFIER_FAN: (
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM1],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM2],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM10],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.HUMIDITY],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.TEMPERATURE],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.MONITORING_ENABLED],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.ODOR_LEVEL],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.TOTAL_POLLUTION_LEVEL],
        TIMER_SENSOR_DESC[TimerProperty.SLEEP_TIMER_RELATIVE_TO_STOP],
        TIME_SENSOR_DESC[TimerProperty.ABSOLUTE_TO_START],
        TIME_SENSOR_DESC[TimerProperty.ABSOLUTE_TO_STOP],
    ),
    DeviceType.AIR_PURIFIER: (
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM1],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM2],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM10],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.HUMIDITY],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.MONITORING_ENABLED],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.ODOR_LEVEL],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.TOTAL_POLLUTION_LEVEL],
        FILTER_INFO_SENSOR_DESC[ThinQProperty.FILTER_REMAIN_PERCENT],
        JOB_MODE_SENSOR_DESC[ThinQProperty.CURRENT_JOB_MODE],
        JOB_MODE_SENSOR_DESC[ThinQProperty.PERSONALIZATION_MODE],
        TIME_SENSOR_DESC[TimerProperty.ABSOLUTE_TO_START],
        TIME_SENSOR_DESC[TimerProperty.ABSOLUTE_TO_STOP],
    ),
    DeviceType.COOKTOP: (
        RUN_STATE_SENSOR_DESC[ThinQProperty.CURRENT_STATE],
        POWER_SENSOR_DESC[ThinQProperty.POWER_LEVEL],
    ),
    DeviceType.DEHUMIDIFIER: (
        JOB_MODE_SENSOR_DESC[ThinQProperty.CURRENT_JOB_MODE],
        HUMIDITY_SENSOR_DESC[ThinQProperty.CURRENT_HUMIDITY],
    ),
    DeviceType.DISH_WASHER: (
        DISH_WASHING_COURSE_SENSOR_DESC[ThinQProperty.CURRENT_DISH_WASHING_COURSE],
        PREFERENCE_SENSOR_DESC[ThinQProperty.RINSE_LEVEL],
        PREFERENCE_SENSOR_DESC[ThinQProperty.SOFTENING_LEVEL],
        RUN_STATE_SENSOR_DESC[ThinQProperty.CURRENT_STATE],
        TIMER_SENSOR_DESC[TimerProperty.TOTAL],
        TIMER_SENSOR_DESC[TimerProperty.RELATIVE_TO_START_WM],
        TIMER_SENSOR_DESC[TimerProperty.REMAIN],
    ),
    DeviceType.DRYER: WASHER_SENSORS,
    DeviceType.HOME_BREW: (
        RECIPE_SENSOR_DESC[ThinQProperty.RECIPE_NAME],
        RECIPE_SENSOR_DESC[ThinQProperty.WORT_INFO],
        RECIPE_SENSOR_DESC[ThinQProperty.YEAST_INFO],
        RECIPE_SENSOR_DESC[ThinQProperty.HOP_OIL_INFO],
        RECIPE_SENSOR_DESC[ThinQProperty.FLAVOR_INFO],
        RECIPE_SENSOR_DESC[ThinQProperty.BEER_REMAIN],
        RUN_STATE_SENSOR_DESC[ThinQProperty.CURRENT_STATE],
        ELAPSED_DAY_SENSOR_DESC[ThinQProperty.ELAPSED_DAY_STATE],
        ELAPSED_DAY_SENSOR_DESC[ThinQProperty.ELAPSED_DAY_TOTAL],
    ),
    DeviceType.HUMIDIFIER: (
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM1],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM2],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM10],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.HUMIDITY],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.TEMPERATURE],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.MONITORING_ENABLED],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.TOTAL_POLLUTION_LEVEL],
        TIMER_SENSOR_DESC[TimerProperty.SLEEP_TIMER_RELATIVE_TO_STOP],
        TIME_SENSOR_DESC[TimerProperty.ABSOLUTE_TO_START],
        TIME_SENSOR_DESC[TimerProperty.ABSOLUTE_TO_STOP],
    ),
    DeviceType.KIMCHI_REFRIGERATOR: (
        REFRIGERATION_SENSOR_DESC[ThinQProperty.FRESH_AIR_FILTER],
        SensorEntityDescription(
            key=ThinQProperty.TARGET_TEMPERATURE,
            translation_key=ThinQProperty.TARGET_TEMPERATURE,
        ),
    ),
    DeviceType.MICROWAVE_OVEN: (RUN_STATE_SENSOR_DESC[ThinQProperty.CURRENT_STATE],),
    DeviceType.OVEN: (
        RUN_STATE_SENSOR_DESC[ThinQProperty.CURRENT_STATE],
        TEMPERATURE_SENSOR_DESC[ThinQProperty.TARGET_TEMPERATURE],
    ),
    DeviceType.PLANT_CULTIVATOR: (
        LIGHT_SENSOR_DESC[ThinQProperty.BRIGHTNESS],
        LIGHT_SENSOR_DESC[ThinQProperty.DURATION],
        RUN_STATE_SENSOR_DESC[ThinQProperty.CURRENT_STATE],
        RUN_STATE_SENSOR_DESC[ThinQProperty.GROWTH_MODE],
        RUN_STATE_SENSOR_DESC[ThinQProperty.WIND_VOLUME],
        TEMPERATURE_SENSOR_DESC[ThinQProperty.DAY_TARGET_TEMPERATURE],
        TEMPERATURE_SENSOR_DESC[ThinQProperty.NIGHT_TARGET_TEMPERATURE],
        TEMPERATURE_SENSOR_DESC[ThinQProperty.TEMPERATURE_STATE],
        TIME_SENSOR_DESC[TimerProperty.LIGHT_START],
    ),
    DeviceType.REFRIGERATOR: (
        REFRIGERATION_SENSOR_DESC[ThinQProperty.FRESH_AIR_FILTER],
        WATER_FILTER_INFO_SENSOR_DESC[ThinQProperty.USED_TIME],
    ),
    DeviceType.ROBOT_CLEANER: (
        RUN_STATE_SENSOR_DESC[ThinQProperty.CURRENT_STATE],
        JOB_MODE_SENSOR_DESC[ThinQProperty.CURRENT_JOB_MODE],
        TIMER_SENSOR_DESC[TimerProperty.RUNNING],
        TIME_SENSOR_DESC[TimerProperty.ABSOLUTE_TO_START],
    ),
    DeviceType.STICK_CLEANER: (
        BATTERY_SENSOR_DESC[ThinQProperty.BATTERY_PERCENT],
        JOB_MODE_SENSOR_DESC[ThinQPropertyEx.CURRENT_JOB_MODE_STICK_CLEANER],
        RUN_STATE_SENSOR_DESC[ThinQProperty.CURRENT_STATE],
    ),
    DeviceType.STYLER: WASHER_SENSORS,
    DeviceType.SYSTEM_BOILER: (
        TEMPERATURE_SENSOR_DESC[ThinQPropertyEx.ROOM_AIR_CURRENT_TEMPERATURE],
        TEMPERATURE_SENSOR_DESC[ThinQPropertyEx.ROOM_IN_WATER_CURRENT_TEMPERATURE],
        TEMPERATURE_SENSOR_DESC[ThinQPropertyEx.ROOM_OUT_WATER_CURRENT_TEMPERATURE],
    ),
    DeviceType.WASHCOMBO_MAIN: WASHER_SENSORS,
    DeviceType.WASHCOMBO_MINI: WASHER_SENSORS,
    DeviceType.WASHER: WASHER_SENSORS,
    DeviceType.WASHTOWER_DRYER: WASHER_SENSORS,
    DeviceType.WASHTOWER: WASHER_SENSORS,
    DeviceType.WASHTOWER_WASHER: WASHER_SENSORS,
    DeviceType.WATER_HEATER: (
        TEMPERATURE_SENSOR_DESC[ThinQProperty.CURRENT_TEMPERATURE],
    ),
    DeviceType.WATER_PURIFIER: (
        RUN_STATE_SENSOR_DESC[ThinQProperty.COCK_STATE],
        RUN_STATE_SENSOR_DESC[ThinQProperty.STERILIZING_STATE],
        WATER_INFO_SENSOR_DESC[ThinQProperty.WATER_TYPE],
    ),
}

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up an entry for sensor platform."""
    entities: list[ThinQSensorEntity] = []
    for coordinator in entry.runtime_data.coordinators.values():
        if (
            descriptions := DEVICE_TYPE_SENSOR_MAP.get(
                coordinator.api.device.device_type
            )
        ) is not None:
            for description in descriptions:
                entities.extend(
                    ThinQSensorEntity(coordinator, description, property_id)
                    for property_id in coordinator.api.get_active_idx(
                        description.key,
                        (
                            ActiveMode.READABLE
                            if (
                                coordinator.api.device.device_type == DeviceType.COOKTOP
                                or isinstance(description.key, TimerProperty)
                            )
                            else ActiveMode.READ_ONLY
                        ),
                    )
                )

    if entities:
        async_add_entities(entities)


class ThinQSensorEntity(ThinQEntity, SensorEntity):
    """Represent a thinq sensor platform."""

    def __init__(
        self,
        coordinator: DeviceDataUpdateCoordinator,
        entity_description: SensorEntityDescription,
        property_id: str,
    ) -> None:
        """Initialize a sensor entity."""
        super().__init__(coordinator, entity_description, property_id)

        if entity_description.device_class == SensorDeviceClass.ENUM:
            self._attr_options = self.data.options

        self._device_state: str | None = None
        self._device_state_id = (
            ThinQProperty.CURRENT_STATE
            if self.location is None
            else f"{self.location}_{ThinQProperty.CURRENT_STATE}"
        )

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        value = self.data.value

        if isinstance(value, time):
            local_now = datetime.now(
                tz=dt_util.get_time_zone(self.coordinator.hass.config.time_zone)
            )
            self._device_state = (
                self.coordinator.data[self._device_state_id].value
                if self._device_state_id in self.coordinator.data
                else None
            )
            if value in [0, None, time.min] or (
                self._device_state == "power_off"
                and self.entity_description.key
                in [TimerProperty.REMAIN, TimerProperty.TOTAL]
            ):
                # Reset to None when power_off
                value = None
            elif self.entity_description.device_class == SensorDeviceClass.TIMESTAMP:
                if self.entity_description.key in TIME_SENSOR_DESC:
                    # Set timestamp for absolute time
                    value = local_now.replace(hour=value.hour, minute=value.minute)
                else:
                    # Set timestamp for delta
                    event_data = timedelta(
                        hours=value.hour, minutes=value.minute, seconds=value.second
                    )
                    new_time = (
                        (local_now - event_data)
                        if self.entity_description.key == TimerProperty.RUNNING
                        else (local_now + event_data)
                    )
                    # The remain_time may change during the wash/dry operation depending on various reasons.
                    # If there is a diff of more than 60sec, the new timestamp is used
                    if (
                        parse_native_value := dt_util.parse_datetime(
                            str(self.native_value)
                        )
                    ) is None or abs(new_time - parse_native_value) > timedelta(
                        seconds=60
                    ):
                        value = new_time
                    else:
                        value = self.native_value
            elif self.entity_description.device_class == SensorDeviceClass.DURATION:
                # Set duration
                value = self._get_duration(
                    value, self.entity_description.native_unit_of_measurement
                )
        self._attr_native_value = value

        if (data_unit := self._get_unit_of_measurement(self.data.unit)) is not None:
            # For different from description's unit
            self._attr_native_unit_of_measurement = data_unit

        _LOGGER.debug(
            "[%s:%s] update status: %s -> %s, options:%s, unit:%s",
            self.coordinator.device_name,
            self.property_id,
            self.data.value,
            self.native_value,
            self.options,
            self.native_unit_of_measurement,
        )

    def _get_duration(self, data: time, unit: str | None) -> float | None:
        if unit == UnitOfTime.MINUTES:
            return (data.hour * 60) + data.minute
        if unit == UnitOfTime.SECONDS:
            return (data.hour * 3600) + (data.minute * 60) + data.second
        return 0
