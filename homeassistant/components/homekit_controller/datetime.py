"""Support for Homekit datetime entities."""

from __future__ import annotations

from aiohomekit.model.characteristics import Characteristic, CharacteristicsTypes

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import KNOWN_DEVICES
from .connection import HKDevice
from .ecobee import EcobeeHoldUntilDatetime


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Homekit datetime entities."""
    hkid: str = config_entry.data["AccessoryPairingID"]
    conn: HKDevice = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_characteristic(char: Characteristic) -> bool:
        if char.type != CharacteristicsTypes.VENDOR_ECOBEE_NEXT_SCHEDULED_CHANGE_TIME:
            return False

        info = {"aid": char.service.accessory.aid, "iid": char.service.iid}

        datetime_entity = EcobeeHoldUntilDatetime(conn, info, char)
        conn.async_migrate_unique_id(
            datetime_entity.old_unique_id, datetime_entity.unique_id, Platform.DATETIME
        )
        async_add_entities([datetime_entity])
        return True

    conn.add_char_factory(async_add_characteristic)
