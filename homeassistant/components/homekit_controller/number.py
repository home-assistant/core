"""
Support for Homekit number ranges.

These are mostly used where a HomeKit accessory exposes additional non-standard
characteristics that don't map to a Home Assistant feature.
"""
from __future__ import annotations

from aiohomekit.model.characteristics import Characteristic, CharacteristicsTypes

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.core import callback

from . import KNOWN_DEVICES, CharacteristicEntity

NUMBER_ENTITIES: dict[str, NumberEntityDescription] = {
    CharacteristicsTypes.Vendor.VOCOLINC_HUMIDIFIER_SPRAY_LEVEL: NumberEntityDescription(
        key=CharacteristicsTypes.Vendor.VOCOLINC_HUMIDIFIER_SPRAY_LEVEL,
        name="Spray Quantity",
        icon="mdi:water",
    ),
    CharacteristicsTypes.Vendor.EVE_DEGREE_ELEVATION: NumberEntityDescription(
        key=CharacteristicsTypes.Vendor.EVE_DEGREE_ELEVATION,
        name="Elevation",
        icon="mdi:elevation-rise",
    ),
}


async def async_setup_entry(hass, config_entry, async_add_entities):
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
