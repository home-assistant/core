"""
Support for Homekit number ranges.

These are mostly used where a HomeKit accessory exposes additional non-standard
characteristics that don't map to a Home Assistant feature.
"""
from __future__ import annotations

from aiohomekit.model.characteristics import Characteristic, CharacteristicsTypes

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KNOWN_DEVICES, CharacteristicEntity

NUMBER_ENTITIES: dict[str, NumberEntityDescription] = {
    CharacteristicsTypes.Vendor.VOCOLINC_HUMIDIFIER_SPRAY_LEVEL: NumberEntityDescription(
        key=CharacteristicsTypes.Vendor.VOCOLINC_HUMIDIFIER_SPRAY_LEVEL,
        name="Spray Quantity",
        icon="mdi:water",
        entity_category=EntityCategory.CONFIG,
    ),
    CharacteristicsTypes.Vendor.EVE_DEGREE_ELEVATION: NumberEntityDescription(
        key=CharacteristicsTypes.Vendor.EVE_DEGREE_ELEVATION,
        name="Elevation",
        icon="mdi:elevation-rise",
        entity_category=EntityCategory.CONFIG,
    ),
    CharacteristicsTypes.Vendor.AQARA_GATEWAY_VOLUME: NumberEntityDescription(
        key=CharacteristicsTypes.Vendor.AQARA_GATEWAY_VOLUME,
        name="Volume",
        icon="mdi:volume-high",
        entity_category=EntityCategory.CONFIG,
    ),
    CharacteristicsTypes.Vendor.AQARA_E1_GATEWAY_VOLUME: NumberEntityDescription(
        key=CharacteristicsTypes.Vendor.AQARA_E1_GATEWAY_VOLUME,
        name="Volume",
        icon="mdi:volume-high",
        entity_category=EntityCategory.CONFIG,
    ),
    CharacteristicsTypes.Vendor.ECOBEE_HOME_TARGET_COOL: NumberEntityDescription(
        key=CharacteristicsTypes.Vendor.ECOBEE_HOME_TARGET_COOL,
        name="Home Cool Target",
        icon="mdi:thermometer-minus",
        entity_category=EntityCategory.CONFIG,
    ),
    CharacteristicsTypes.Vendor.ECOBEE_HOME_TARGET_HEAT: NumberEntityDescription(
        key=CharacteristicsTypes.Vendor.ECOBEE_HOME_TARGET_HEAT,
        name="Home Heat Target",
        icon="mdi:thermometer-plus",
        entity_category=EntityCategory.CONFIG,
    ),
    CharacteristicsTypes.Vendor.ECOBEE_SLEEP_TARGET_COOL: NumberEntityDescription(
        key=CharacteristicsTypes.Vendor.ECOBEE_SLEEP_TARGET_COOL,
        name="Sleep Cool Target",
        icon="mdi:thermometer-minus",
        entity_category=EntityCategory.CONFIG,
    ),
    CharacteristicsTypes.Vendor.ECOBEE_SLEEP_TARGET_HEAT: NumberEntityDescription(
        key=CharacteristicsTypes.Vendor.ECOBEE_SLEEP_TARGET_HEAT,
        name="Sleep Heat Target",
        icon="mdi:thermometer-plus",
        entity_category=EntityCategory.CONFIG,
    ),
    CharacteristicsTypes.Vendor.ECOBEE_AWAY_TARGET_COOL: NumberEntityDescription(
        key=CharacteristicsTypes.Vendor.ECOBEE_AWAY_TARGET_COOL,
        name="Away Cool Target",
        icon="mdi:thermometer-minus",
        entity_category=EntityCategory.CONFIG,
    ),
    CharacteristicsTypes.Vendor.ECOBEE_AWAY_TARGET_HEAT: NumberEntityDescription(
        key=CharacteristicsTypes.Vendor.ECOBEE_AWAY_TARGET_HEAT,
        name="Away Heat Target",
        icon="mdi:thermometer-plus",
        entity_category=EntityCategory.CONFIG,
    ),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homekit numbers."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_characteristic(char: Characteristic):
        if not (description := NUMBER_ENTITIES.get(char.type)):
            return False
        info = {"aid": char.service.accessory.aid, "iid": char.service.iid}
        async_add_entities([HomeKitNumber(conn, info, char, description)], True)
        return True

    conn.add_char_factory(async_add_characteristic)


class HomeKitNumber(CharacteristicEntity, NumberEntity):
    """Representation of a Number control on a homekit accessory."""

    def __init__(
        self,
        conn,
        info,
        char,
        description: NumberEntityDescription,
    ):
        """Initialise a HomeKit number control."""
        self.entity_description = description
        super().__init__(conn, info, char)

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        if prefix := super().name:
            return f"{prefix} {self.entity_description.name}"
        return self.entity_description.name

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [self._char.type]

    @property
    def min_value(self) -> float:
        """Return the minimum value."""
        return self._char.minValue

    @property
    def max_value(self) -> float:
        """Return the maximum value."""
        return self._char.maxValue

    @property
    def step(self) -> float:
        """Return the increment/decrement step."""
        return self._char.minStep

    @property
    def value(self) -> float:
        """Return the current characteristic value."""
        return self._char.value

    async def async_set_value(self, value: float):
        """Set the characteristic to this value."""
        await self.async_put_characteristics(
            {
                self._char.type: value,
            }
        )
