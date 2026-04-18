"""Button platform for the Flipper IR integration."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import FlipperIRConfigEntry
from .const import DOMAIN, EVENT_BUTTON_PRESSED

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FlipperIRConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Flipper IR buttons from a config entry."""
    async_add_entities(
        FlipperIRButton(entry, command) for command in entry.runtime_data
    )


class FlipperIRButton(ButtonEntity):
    """Representation of a single Flipper IR command as a button."""

    _attr_has_entity_name = True

    def __init__(
        self, entry: FlipperIRConfigEntry, command: dict[str, str]
    ) -> None:
        """Initialize the button."""
        self._entry_id = entry.entry_id
        self._command = command
        command_name = command["name"]
        self._attr_name = command_name
        self._attr_unique_id = f"{entry.entry_id}_{command_name}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.data[CONF_NAME],
            manufacturer="Flipper Devices",
            model="IR Remote",
        )

    async def async_press(self) -> None:
        """Fire an event representing a press of this IR command."""
        self.hass.bus.async_fire(
            EVENT_BUTTON_PRESSED,
            {
                "entry_id": self._entry_id,
                "command": self._command,
            },
        )
