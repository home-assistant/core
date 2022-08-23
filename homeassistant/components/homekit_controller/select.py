"""Support for Homekit select entities."""
from __future__ import annotations

from aiohomekit.model.characteristics import Characteristic, CharacteristicsTypes

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import KNOWN_DEVICES
from .const import DEVICE_CLASS_ECOBEE_MODE
from .entity import CharacteristicEntity

_ECOBEE_MODE_TO_TEXT = {
    0: "home",
    1: "sleep",
    2: "away",
}
_ECOBEE_MODE_TO_NUMBERS = {v: k for (k, v) in _ECOBEE_MODE_TO_TEXT.items()}


class EcobeeModeSelect(CharacteristicEntity, SelectEntity):
    """Represents a ecobee mode select entity."""

    _attr_options = ["home", "sleep", "away"]
    _attr_device_class = DEVICE_CLASS_ECOBEE_MODE

    @property
    def name(self) -> str:
        """Return the name of the device if any."""
        if name := super().name:
            return f"{name} Current Mode"
        return "Current Mode"

    def get_characteristic_types(self) -> list[str]:
        """Define the homekit characteristics the entity cares about."""
        return [
            CharacteristicsTypes.VENDOR_ECOBEE_CURRENT_MODE,
        ]

    @property
    def current_option(self) -> str | None:
        """Return the current selected option."""
        return _ECOBEE_MODE_TO_TEXT.get(self._char.value)

    async def async_select_option(self, option: str) -> None:
        """Set the current mode."""
        option_int = _ECOBEE_MODE_TO_NUMBERS[option]
        await self.async_put_characteristics(
            {CharacteristicsTypes.VENDOR_ECOBEE_SET_HOLD_SCHEDULE: option_int}
        )


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homekit select entities."""
    hkid = config_entry.data["AccessoryPairingID"]
    conn = hass.data[KNOWN_DEVICES][hkid]

    @callback
    def async_add_characteristic(char: Characteristic) -> bool:
        if char.type == CharacteristicsTypes.VENDOR_ECOBEE_CURRENT_MODE:
            info = {"aid": char.service.accessory.aid, "iid": char.service.iid}
            async_add_entities([EcobeeModeSelect(conn, info, char)])
            return True
        return False

    conn.add_char_factory(async_add_characteristic)
