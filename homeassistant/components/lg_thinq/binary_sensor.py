"""Support for binary sensor entities."""

from __future__ import annotations

from thinqconnect import PROPERTY_READABLE, DeviceType
from thinqconnect.devices.const import Property as ThinQProperty
from thinqconnect.integration.homeassistant.property import create_properties

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
                coordinator.device_api.device_type
            )
        ) is not None:
            for description in descriptions:
                properties = create_properties(
                    device_api=coordinator.device_api,
                    key=description.key,
                    children_keys=None,
                    rw_type=PROPERTY_READABLE,
                )
                if not properties:
                    continue

                entities.extend(
                    ThinQBinarySensorEntity(coordinator, description, prop)
                    for prop in properties
                )

    if entities:
        async_add_entities(entities)


class ThinQBinarySensorEntity(ThinQEntity, BinarySensorEntity):
    """Represent a thinq binary sensor platform."""

    def _update_status(self) -> None:
        """Update status itself."""
        super()._update_status()

        self._attr_is_on = self.property.get_value_as_bool()
