"""Support for Homekit number ranges.

These are mostly used where a HomeKit accessory exposes additional non-standard
characteristics that don't map to a Home Assistant feature.
"""

from typing import override

from aiohomekit.model.characteristics import Characteristic, CharacteristicsTypes

from homeassistant.components.number import (
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    DEFAULT_STEP,
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, Platform, UnitOfTime
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import ConfigType

from . import KNOWN_DEVICES
from .connection import HKDevice
from .entity import CharacteristicEntity

NUMBER_ENTITIES: dict[str, NumberEntityDescription] = {
    CharacteristicsTypes.VENDOR_VOCOLINC_HUMIDIFIER_SPRAY_LEVEL: (
        NumberEntityDescription(
            key=CharacteristicsTypes.VENDOR_VOCOLINC_HUMIDIFIER_SPRAY_LEVEL,
            translation_key="spray_quantity",
            entity_category=EntityCategory.CONFIG,
        )
    ),
    CharacteristicsTypes.VENDOR_EVE_DEGREE_ELEVATION: NumberEntityDescription(
        key=CharacteristicsTypes.VENDOR_EVE_DEGREE_ELEVATION,
        translation_key="elevation",
        entity_category=EntityCategory.CONFIG,
    ),
    CharacteristicsTypes.VENDOR_AQARA_GATEWAY_VOLUME: NumberEntityDescription(
        key=CharacteristicsTypes.VENDOR_AQARA_GATEWAY_VOLUME,
        translation_key="volume",
        entity_category=EntityCategory.CONFIG,
    ),
    CharacteristicsTypes.VENDOR_AQARA_E1_GATEWAY_VOLUME: NumberEntityDescription(
        key=CharacteristicsTypes.VENDOR_AQARA_E1_GATEWAY_VOLUME,
        translation_key="volume",
        entity_category=EntityCategory.CONFIG,
    ),
    CharacteristicsTypes.VENDOR_EVE_MOTION_DURATION: NumberEntityDescription(
        key=CharacteristicsTypes.VENDOR_EVE_MOTION_DURATION,
        translation_key="duration",
        entity_category=EntityCategory.CONFIG,
    ),
    CharacteristicsTypes.VENDOR_EVE_MOTION_SENSITIVITY: NumberEntityDescription(
        key=CharacteristicsTypes.VENDOR_EVE_MOTION_SENSITIVITY,
        translation_key="sensitivity",
        entity_category=EntityCategory.CONFIG,
    ),
    CharacteristicsTypes.SET_DURATION: NumberEntityDescription(
        key=CharacteristicsTypes.SET_DURATION,
        device_class=NumberDeviceClass.DURATION,
        translation_key="duration",
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfTime.SECONDS,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Homekit numbers."""
    hkid: str = config_entry.data["AccessoryPairingID"]
    conn: HKDevice = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_characteristic(char: Characteristic) -> bool:
        entities: list[HomeKitNumber] = []
        info = {"aid": char.service.accessory.aid, "iid": char.service.iid}

        if description := NUMBER_ENTITIES.get(char.type):
            entities.append(HomeKitNumber(conn, info, char, description))
        else:
            return False

        for entity in entities:
            conn.async_migrate_unique_id(
                entity.old_unique_id, entity.unique_id, Platform.NUMBER
            )

        async_add_entities(entities)
        return True

    conn.add_char_factory(async_add_characteristic)


class HomeKitNumber(CharacteristicEntity, NumberEntity):
    """Representation of a Number control on a homekit accessory."""

    def __init__(
        self,
        conn: HKDevice,
        info: ConfigType,
        char: Characteristic,
        description: NumberEntityDescription,
    ) -> None:
        """Initialise a HomeKit number control."""
        self.entity_description = description
        super().__init__(conn, info, char)

    @override
    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity is tracking."""
        return [self._char.type]

    @property
    @override
    def native_min_value(self) -> float:
        """Return the minimum value."""
        return self._char.minValue or DEFAULT_MIN_VALUE

    @property
    @override
    def native_max_value(self) -> float:
        """Return the maximum value."""
        return self._char.maxValue or DEFAULT_MAX_VALUE

    @property
    @override
    def native_step(self) -> float:
        """Return the increment/decrement step."""
        return self._char.minStep or DEFAULT_STEP

    @property
    @override
    def native_value(self) -> float:
        """Return the current characteristic value."""
        return self._char.value

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Set the characteristic to this value."""
        await self.async_put_characteristics(
            {
                self._char.type: value,
            }
        )
