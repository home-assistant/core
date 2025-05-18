"""Support for binary sensor entities."""

from __future__ import annotations

from dataclasses import dataclass
import logging

from thinqconnect import DeviceType
from thinqconnect.devices.const import Property as ThinQProperty
from thinqconnect.integration import ActiveMode

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ThinqConfigEntry
from .entity import ThinQEntity


@dataclass(frozen=True, kw_only=True)
class ThinQBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describes ThinQ sensor entity."""

    on_key: str | None = None


BINARY_SENSOR_DESC: dict[ThinQProperty, ThinQBinarySensorEntityDescription] = {
    ThinQProperty.RINSE_REFILL: ThinQBinarySensorEntityDescription(
        key=ThinQProperty.RINSE_REFILL,
        translation_key=ThinQProperty.RINSE_REFILL,
    ),
    ThinQProperty.ECO_FRIENDLY_MODE: ThinQBinarySensorEntityDescription(
        key=ThinQProperty.ECO_FRIENDLY_MODE,
        translation_key=ThinQProperty.ECO_FRIENDLY_MODE,
    ),
    ThinQProperty.POWER_SAVE_ENABLED: ThinQBinarySensorEntityDescription(
        key=ThinQProperty.POWER_SAVE_ENABLED,
        translation_key=ThinQProperty.POWER_SAVE_ENABLED,
    ),
    ThinQProperty.REMOTE_CONTROL_ENABLED: ThinQBinarySensorEntityDescription(
        key=ThinQProperty.REMOTE_CONTROL_ENABLED,
        translation_key=ThinQProperty.REMOTE_CONTROL_ENABLED,
    ),
    ThinQProperty.SABBATH_MODE: ThinQBinarySensorEntityDescription(
        key=ThinQProperty.SABBATH_MODE,
        translation_key=ThinQProperty.SABBATH_MODE,
    ),
    ThinQProperty.DOOR_STATE: ThinQBinarySensorEntityDescription(
        key=ThinQProperty.DOOR_STATE,
        device_class=BinarySensorDeviceClass.DOOR,
        on_key="open",
    ),
    ThinQProperty.MACHINE_CLEAN_REMINDER: ThinQBinarySensorEntityDescription(
        key=ThinQProperty.MACHINE_CLEAN_REMINDER,
        translation_key=ThinQProperty.MACHINE_CLEAN_REMINDER,
        on_key="mcreminder_on",
    ),
    ThinQProperty.SIGNAL_LEVEL: ThinQBinarySensorEntityDescription(
        key=ThinQProperty.SIGNAL_LEVEL,
        translation_key=ThinQProperty.SIGNAL_LEVEL,
        on_key="signallevel_on",
    ),
    ThinQProperty.CLEAN_LIGHT_REMINDER: ThinQBinarySensorEntityDescription(
        key=ThinQProperty.CLEAN_LIGHT_REMINDER,
        translation_key=ThinQProperty.CLEAN_LIGHT_REMINDER,
        on_key="cleanlreminder_on",
    ),
    ThinQProperty.HOOD_OPERATION_MODE: ThinQBinarySensorEntityDescription(
        key=ThinQProperty.HOOD_OPERATION_MODE,
        translation_key="operation_mode",
        on_key="power_on",
    ),
    ThinQProperty.WATER_HEATER_OPERATION_MODE: ThinQBinarySensorEntityDescription(
        key=ThinQProperty.WATER_HEATER_OPERATION_MODE,
        device_class=BinarySensorDeviceClass.POWER,
        translation_key=ThinQProperty.WATER_HEATER_OPERATION_MODE,
        on_key="power_on",
    ),
    ThinQProperty.ONE_TOUCH_FILTER: ThinQBinarySensorEntityDescription(
        key=ThinQProperty.ONE_TOUCH_FILTER,
        translation_key=ThinQProperty.ONE_TOUCH_FILTER,
        on_key="on",
    ),
}

DEVICE_TYPE_BINARY_SENSOR_MAP: dict[
    DeviceType, tuple[ThinQBinarySensorEntityDescription, ...]
] = {
    DeviceType.COOKTOP: (BINARY_SENSOR_DESC[ThinQProperty.REMOTE_CONTROL_ENABLED],),
    DeviceType.DISH_WASHER: (
        BINARY_SENSOR_DESC[ThinQProperty.DOOR_STATE],
        BINARY_SENSOR_DESC[ThinQProperty.RINSE_REFILL],
        BINARY_SENSOR_DESC[ThinQProperty.REMOTE_CONTROL_ENABLED],
        BINARY_SENSOR_DESC[ThinQProperty.MACHINE_CLEAN_REMINDER],
        BINARY_SENSOR_DESC[ThinQProperty.SIGNAL_LEVEL],
        BINARY_SENSOR_DESC[ThinQProperty.CLEAN_LIGHT_REMINDER],
    ),
    DeviceType.DRYER: (BINARY_SENSOR_DESC[ThinQProperty.REMOTE_CONTROL_ENABLED],),
    DeviceType.HOOD: (BINARY_SENSOR_DESC[ThinQProperty.HOOD_OPERATION_MODE],),
    DeviceType.OVEN: (BINARY_SENSOR_DESC[ThinQProperty.REMOTE_CONTROL_ENABLED],),
    DeviceType.REFRIGERATOR: (
        BINARY_SENSOR_DESC[ThinQProperty.DOOR_STATE],
        BINARY_SENSOR_DESC[ThinQProperty.ECO_FRIENDLY_MODE],
        BINARY_SENSOR_DESC[ThinQProperty.POWER_SAVE_ENABLED],
        BINARY_SENSOR_DESC[ThinQProperty.SABBATH_MODE],
    ),
    DeviceType.KIMCHI_REFRIGERATOR: (
        BINARY_SENSOR_DESC[ThinQProperty.ONE_TOUCH_FILTER],
    ),
    DeviceType.STYLER: (BINARY_SENSOR_DESC[ThinQProperty.REMOTE_CONTROL_ENABLED],),
    DeviceType.WASHCOMBO_MAIN: (
        BINARY_SENSOR_DESC[ThinQProperty.REMOTE_CONTROL_ENABLED],
    ),
    DeviceType.WASHCOMBO_MINI: (
        BINARY_SENSOR_DESC[ThinQProperty.REMOTE_CONTROL_ENABLED],
    ),
    DeviceType.WASHER: (BINARY_SENSOR_DESC[ThinQProperty.REMOTE_CONTROL_ENABLED],),
    DeviceType.WASHTOWER_DRYER: (
        BINARY_SENSOR_DESC[ThinQProperty.REMOTE_CONTROL_ENABLED],
    ),
    DeviceType.WASHTOWER: (BINARY_SENSOR_DESC[ThinQProperty.REMOTE_CONTROL_ENABLED],),
    DeviceType.WASHTOWER_WASHER: (
        BINARY_SENSOR_DESC[ThinQProperty.REMOTE_CONTROL_ENABLED],
    ),
    DeviceType.WATER_HEATER: (
        BINARY_SENSOR_DESC[ThinQProperty.WATER_HEATER_OPERATION_MODE],
    ),
    DeviceType.WINE_CELLAR: (BINARY_SENSOR_DESC[ThinQProperty.SABBATH_MODE],),
}
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up an entry for binary sensor platform."""
    entities: list[ThinQBinarySensorEntity] = []
    for coordinator in entry.runtime_data.coordinators.values():
        if (
            descriptions := DEVICE_TYPE_BINARY_SENSOR_MAP.get(
                coordinator.api.device.device_type
            )
        ) is not None:
            for description in descriptions:
                entities.extend(
                    ThinQBinarySensorEntity(coordinator, description, property_id)
                    for property_id in coordinator.api.get_active_idx(
                        description.key, ActiveMode.READ_ONLY
                    )
                )

    if entities:
        async_add_entities(entities)


class ThinQBinarySensorEntity(ThinQEntity, BinarySensorEntity):
    """Represent a thinq binary sensor platform."""

    entity_description: ThinQBinarySensorEntityDescription

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        if (key := self.entity_description.on_key) is not None:
            self._attr_is_on = self.data.value == key
        else:
            self._attr_is_on = self.data.is_on

        _LOGGER.debug(
            "[%s:%s] update status: %s -> %s",
            self.coordinator.device_name,
            self.property_id,
            self.data.value,
            self.is_on,
        )
