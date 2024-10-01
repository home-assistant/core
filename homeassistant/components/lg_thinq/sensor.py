"""Support for sensor entities."""

from __future__ import annotations

import logging

from thinqconnect import DeviceType
from thinqconnect.devices.const import Property as ThinQProperty
from thinqconnect.integration import ActiveMode, ThinQPropertyEx

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
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ThinqConfigEntry
from .coordinator import DeviceDataUpdateCoordinator
from .entity import ThinQEntity

ERROR_DESC = SensorEntityDescription(
    key=ThinQPropertyEx.ERROR,
    device_class=SensorDeviceClass.ENUM,
    translation_key=ThinQPropertyEx.ERROR,
)

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
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=ThinQProperty.TEMPERATURE,
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
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        translation_key=ThinQProperty.TARGET_TEMPERATURE,
    ),
    ThinQProperty.DAY_TARGET_TEMPERATURE: SensorEntityDescription(
        key=ThinQProperty.DAY_TARGET_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        translation_key=ThinQProperty.DAY_TARGET_TEMPERATURE,
    ),
    ThinQProperty.NIGHT_TARGET_TEMPERATURE: SensorEntityDescription(
        key=ThinQProperty.NIGHT_TARGET_TEMPERATURE,
        device_class=SensorDeviceClass.TEMPERATURE,
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
}
WATER_INFO_SENSOR_DESC: dict[ThinQProperty, SensorEntityDescription] = {
    ThinQProperty.WATER_TYPE: SensorEntityDescription(
        key=ThinQProperty.WATER_TYPE,
        device_class=SensorDeviceClass.ENUM,
        translation_key=ThinQProperty.WATER_TYPE,
    ),
}
WASHER_SENSORS: tuple[SensorEntityDescription, ...] = (
    ERROR_DESC,
    RUN_STATE_SENSOR_DESC[ThinQProperty.CURRENT_STATE],
)
DEVICE_TYPE_SENSOR_MAP: dict[DeviceType, tuple[SensorEntityDescription, ...]] = {
    DeviceType.AIR_CONDITIONER: (
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM1],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM2],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM10],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.HUMIDITY],
    ),
    DeviceType.AIR_PURIFIER_FAN: (
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM1],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM2],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM10],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.HUMIDITY],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.TEMPERATURE],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.MONITORING_ENABLED],
    ),
    DeviceType.AIR_PURIFIER: (
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM1],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM2],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM10],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.HUMIDITY],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.MONITORING_ENABLED],
        JOB_MODE_SENSOR_DESC[ThinQProperty.CURRENT_JOB_MODE],
        JOB_MODE_SENSOR_DESC[ThinQProperty.PERSONALIZATION_MODE],
    ),
    DeviceType.COOKTOP: (RUN_STATE_SENSOR_DESC[ThinQProperty.CURRENT_STATE],),
    DeviceType.DEHUMIDIFIER: (
        JOB_MODE_SENSOR_DESC[ThinQProperty.CURRENT_JOB_MODE],
        HUMIDITY_SENSOR_DESC[ThinQProperty.CURRENT_HUMIDITY],
    ),
    DeviceType.DISH_WASHER: (
        ERROR_DESC,
        RUN_STATE_SENSOR_DESC[ThinQProperty.CURRENT_STATE],
    ),
    DeviceType.DRYER: WASHER_SENSORS,
    DeviceType.HOME_BREW: (RUN_STATE_SENSOR_DESC[ThinQProperty.CURRENT_STATE],),
    DeviceType.HUMIDIFIER: (
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM1],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM2],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.PM10],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.HUMIDITY],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.TEMPERATURE],
        AIR_QUALITY_SENSOR_DESC[ThinQProperty.MONITORING_ENABLED],
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
        RUN_STATE_SENSOR_DESC[ThinQProperty.CURRENT_STATE],
        RUN_STATE_SENSOR_DESC[ThinQProperty.GROWTH_MODE],
        RUN_STATE_SENSOR_DESC[ThinQProperty.WIND_VOLUME],
        TEMPERATURE_SENSOR_DESC[ThinQProperty.DAY_TARGET_TEMPERATURE],
        TEMPERATURE_SENSOR_DESC[ThinQProperty.NIGHT_TARGET_TEMPERATURE],
        TEMPERATURE_SENSOR_DESC[ThinQProperty.TEMPERATURE_STATE],
    ),
    DeviceType.REFRIGERATOR: (
        REFRIGERATION_SENSOR_DESC[ThinQProperty.FRESH_AIR_FILTER],
    ),
    DeviceType.ROBOT_CLEANER: (
        ERROR_DESC,
        RUN_STATE_SENSOR_DESC[ThinQProperty.CURRENT_STATE],
        JOB_MODE_SENSOR_DESC[ThinQProperty.CURRENT_JOB_MODE],
    ),
    DeviceType.STICK_CLEANER: (
        JOB_MODE_SENSOR_DESC[ThinQPropertyEx.CURRENT_JOB_MODE_STICK_CLEANER],
        RUN_STATE_SENSOR_DESC[ThinQProperty.CURRENT_STATE],
    ),
    DeviceType.STYLER: WASHER_SENSORS,
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
    async_add_entities: AddEntitiesCallback,
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
                        description.key, ActiveMode.READ_ONLY
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

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        self._attr_native_value = self.data.value

        if (data_unit := self._get_unit_of_measurement(self.data.unit)) is not None:
            # For different from description's unit
            self._attr_native_unit_of_measurement = data_unit

        _LOGGER.debug(
            "[%s:%s] update status: %s, options:%s, unit:%s",
            self.coordinator.device_name,
            self.property_id,
            self.data.value,
            self.options,
            self.native_unit_of_measurement,
        )
