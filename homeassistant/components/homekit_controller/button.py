"""
Support for Homekit buttons.

These are mostly used where a HomeKit accessory exposes additional non-standard
characteristics that don't map to a Home Assistant feature.
"""
from __future__ import annotations

from dataclasses import dataclass

from aiohomekit.model.characteristics import Characteristic, CharacteristicsTypes

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KNOWN_DEVICES, CharacteristicEntity


@dataclass
class HomeKitButtonEntityDescription(ButtonEntityDescription):
    """Describes Homekit button."""

    write_value: int | str | None = None


BUTTON_ENTITIES: dict[str, HomeKitButtonEntityDescription] = {
    CharacteristicsTypes.Vendor.HAA_SETUP: HomeKitButtonEntityDescription(
        key=CharacteristicsTypes.Vendor.HAA_SETUP,
        name="Setup",
        icon="mdi:cog",
        entity_category=EntityCategory.CONFIG,
        write_value="#HAA@trcmd",
    ),
    CharacteristicsTypes.Vendor.HAA_UPDATE: HomeKitButtonEntityDescription(
        key=CharacteristicsTypes.Vendor.HAA_UPDATE,
        name="Update",
        device_class=ButtonDeviceClass.UPDATE,
        entity_category=EntityCategory.CONFIG,
        write_value="#HAA@trcmd",
    ),
    CharacteristicsTypes.IDENTIFY: HomeKitButtonEntityDescription(
        key=CharacteristicsTypes.IDENTIFY,
        name="Identify",
        entity_category=EntityCategory.DIAGNOSTIC,
        write_value=True,
    ),
}

# For legacy reasons, "built-in" characteristic types are in their short form
# And vendor types don't have a short form
# This means long and short forms get mixed up in this dict, and comparisons
# don't work!
# We call get_uuid on *every* type to normalise them to the long form
# Eventually aiohomekit will use the long form exclusively amd this can be removed.
for k, v in list(BUTTON_ENTITIES.items()):
    BUTTON_ENTITIES[CharacteristicsTypes.get_uuid(k)] = BUTTON_ENTITIES.pop(k)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homekit buttons."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_characteristic(char: Characteristic):
        if not (description := BUTTON_ENTITIES.get(char.type)):
            return False
        info = {"aid": char.service.accessory.aid, "iid": char.service.iid}
        async_add_entities([HomeKitButton(conn, info, char, description)], True)
        return True

    conn.add_char_factory(async_add_characteristic)


class HomeKitButton(CharacteristicEntity, ButtonEntity):
    """Representation of a Button control on a homekit accessory."""

    entity_description: HomeKitButtonEntityDescription

    def __init__(
        self,
        conn,
        info,
        char,
        description: HomeKitButtonEntityDescription,
    ):
        """Initialise a HomeKit button control."""
        self.entity_description = description
        super().__init__(conn, info, char)

    def get_characteristic_types(self):
        """Define the homekit characteristics the entity is tracking."""
        return [self._char.type]

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        if name := super().name:
            return f"{name} {self.entity_description.name}"
        return f"{self.entity_description.name}"

    async def async_press(self) -> None:
        """Press the button."""
        key = self.entity_description.key
        val = self.entity_description.write_value
        return await self.async_put_characteristics({key: val})
