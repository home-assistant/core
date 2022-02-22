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
        entities = []
        info = {"aid": char.service.accessory.aid, "iid": char.service.iid}

        if description := NUMBER_ENTITIES.get(char.type):
            entities.append(HomeKitNumber(conn, info, char, description))
        elif entity_type := NUMBER_ENTITY_CLASSES.get(char.type):
            entities.append(entity_type(conn, info, char))
        else:
            return False

        async_add_entities(entities, True)
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


class HomeKitEcobeeFanModeNumber(CharacteristicEntity, NumberEntity):
    """Representation of a Number control for Ecobee Fan Mode request."""

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [self._char.type]

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        prefix = ""
        if name := super().name:
            prefix = name
        return f"{prefix} Fan Mode"

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

        # Sending the fan mode request sometimes ends up getting ignored by ecobee
        # and this might be because it the older value instead of newer, and ecobee
        # thinks there is nothing to do.
        # So in order to make sure that the request is executed by ecobee, we need
        # to send a different value before sending the target value.
        # Fan mode value is a value from 0 to 100. We send a value off by 1 first.

        if value > self.min_value:
            other_value = value - 1
        else:
            other_value = self.min_value + 1

        if value != other_value:
            await self.async_put_characteristics(
                {
                    self._char.type: other_value,
                }
            )

        await self.async_put_characteristics(
            {
                self._char.type: value,
            }
        )


NUMBER_ENTITY_CLASSES: dict[str, type] = {
    CharacteristicsTypes.Vendor.ECOBEE_FAN_WRITE_SPEED: HomeKitEcobeeFanModeNumber,
}
