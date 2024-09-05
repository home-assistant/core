"""Support for binary sensor entities."""

from __future__ import annotations

import logging

from thinqconnect import DeviceType
from thinqconnect.devices.const import Property as ThinQProperty

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import ThinqConfigEntry
from .entity import ThinQEntity

BINARY_SENSOR_DESC: dict[ThinQProperty, BinarySensorEntityDescription] = {
    ThinQProperty.RINSE_REFILL: BinarySensorEntityDescription(
        key=ThinQProperty.RINSE_REFILL,
        translation_key=ThinQProperty.RINSE_REFILL,
    ),
    ThinQProperty.ECO_FRIENDLY_MODE: BinarySensorEntityDescription(
        key=ThinQProperty.ECO_FRIENDLY_MODE,
        translation_key=ThinQProperty.ECO_FRIENDLY_MODE,
    ),
    ThinQProperty.POWER_SAVE_ENABLED: BinarySensorEntityDescription(
        key=ThinQProperty.POWER_SAVE_ENABLED,
        translation_key=ThinQProperty.POWER_SAVE_ENABLED,
    ),
    ThinQProperty.REMOTE_CONTROL_ENABLED: BinarySensorEntityDescription(
        key=ThinQProperty.REMOTE_CONTROL_ENABLED,
        translation_key=ThinQProperty.REMOTE_CONTROL_ENABLED,
    ),
    ThinQProperty.SABBATH_MODE: BinarySensorEntityDescription(
        key=ThinQProperty.SABBATH_MODE,
        translation_key=ThinQProperty.SABBATH_MODE,
    ),
}

DEVICE_TYPE_BINARY_SENSOR_MAP: dict[
    DeviceType, tuple[BinarySensorEntityDescription, ...]
] = {
    DeviceType.COOKTOP: (BINARY_SENSOR_DESC[ThinQProperty.REMOTE_CONTROL_ENABLED],),
    DeviceType.DISH_WASHER: (
        BINARY_SENSOR_DESC[ThinQProperty.RINSE_REFILL],
        BINARY_SENSOR_DESC[ThinQProperty.REMOTE_CONTROL_ENABLED],
    ),
    DeviceType.DRYER: (BINARY_SENSOR_DESC[ThinQProperty.REMOTE_CONTROL_ENABLED],),
    DeviceType.OVEN: (BINARY_SENSOR_DESC[ThinQProperty.REMOTE_CONTROL_ENABLED],),
    DeviceType.REFRIGERATOR: (
        BINARY_SENSOR_DESC[ThinQProperty.ECO_FRIENDLY_MODE],
        BINARY_SENSOR_DESC[ThinQProperty.POWER_SAVE_ENABLED],
        BINARY_SENSOR_DESC[ThinQProperty.SABBATH_MODE],
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
    DeviceType.WINE_CELLAR: (BINARY_SENSOR_DESC[ThinQProperty.SABBATH_MODE],),
}
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ThinqConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up an entry for binary sensor platform."""
    entities: list[ThinQBinarySensorEntity] = []
    for coordinator in entry.runtime_data.values():
        if (
            descriptions := DEVICE_TYPE_BINARY_SENSOR_MAP.get(
                coordinator.api.device.device_type
            )
        ) is not None:
            for description in descriptions:
                entities.extend(
                    ThinQBinarySensorEntity(coordinator, description, property_id)
                    for property_id in coordinator.api.get_active_idx(description.key)
                )

    if entities:
        async_add_entities(entities)


class ThinQBinarySensorEntity(ThinQEntity, BinarySensorEntity):
    """Represent a thinq binary sensor platform."""

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        _LOGGER.debug(
            "[%s:%s] update status: %s",
            self.coordinator.device_name,
            self.property_id,
            self.data.is_on,
        )
        self._attr_is_on = self.data.is_on
