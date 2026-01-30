"""Selectors for Lyngdorf Integration."""

from typing import cast

from lyngdorf.device import Receiver

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    ICOM_ROOM_PERFECT_POSITION,
    ICON_SOUND_MODE,
    ICON_SOURCE,
    ICON_VOICING,
)
from .models import LyngdorfConfigEntry

SELECTS = {
    "source": {
        "icon": ICON_SOURCE,
        "name": "Main Source",
        "options_property": "available_sources",
    },
    "sound_mode": {
        "icon": ICON_SOUND_MODE,
        "name": "Sound Mode",
        "options_property": "available_sound_modes",
    },
    "voicing": {
        "icon": ICON_VOICING,
        "name": "Voicing",
        "options_property": "available_voicings",
    },
    "room_perfect_position": {
        "icon": ICOM_ROOM_PERFECT_POSITION,
        "name": "Room Perfect Position",
        "options_property": "available_room_perfect_positions",
    },
    "zone_b_source": {
        "icon": ICON_SOURCE,
        "name": "Zone B Source",
        "options_property": "zone_b_available_sources",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LyngdorfConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the receiver from a config entry."""
    receiver = config_entry.runtime_data.receiver
    device_info = config_entry.runtime_data.device_info

    entities = [
        LyngdorfSelectEntity(
            receiver,
            config_entry,
            device_info,
            prop_name,
            info["name"],
            info["icon"],
            info["options_property"],
        )
        for prop_name, info in SELECTS.items()
    ]

    async_add_entities(entities, update_before_add=True)


class LyngdorfSelectEntity(SelectEntity):
    """Lyngdorf specific selection entity."""

    def __init__(
        self,
        receiver: Receiver,
        config_entry: LyngdorfConfigEntry,
        device_info: DeviceInfo,
        property: str,
        name: str,
        icon: str,
        options_property: str,
    ) -> None:
        """Create a new select Entity."""
        self._attr_has_entity_name = True
        self._attr_device_info = device_info
        self._attr_unique_id = f"{config_entry.unique_id}_{property}"
        self._receiver = receiver
        self._attr_name = name
        self._attr_icon = icon
        self._property = property
        self._options_property = options_property

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        setattr(self._receiver, self._property, option)

    @property
    def current_option(self) -> str | None:
        """Return the selected entity option to represent the entity state."""
        return cast(str, getattr(self._receiver, self._property))

    @property
    def options(self) -> list[str]:
        """Return a set of selectable options."""
        return cast(list[str], getattr(self._receiver, self._options_property))

    async def async_added_to_hass(self) -> None:
        """Notify of addition to haas."""
        self._receiver.register_notification_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Notify of removal from haas."""
        self._receiver.un_register_notification_callback(self.async_write_ha_state)
