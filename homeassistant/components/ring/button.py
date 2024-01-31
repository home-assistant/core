"""Component providing HA sensor support for Ring Buttons."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN
from .entity import RingEntityMixin

BUTTON_DESCRIPTION = ButtonEntityDescription(
    key="open_door",
    name="Open door",
    icon="mdi:door-closed-lock",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Create the buttons for the Ring devices."""
    devices = hass.data[DOMAIN][config_entry.entry_id]["devices"]

    # Some accounts returned data without intercom devices
    devices.setdefault("other", [])

    buttons = []

    for device in devices["other"]:
        if device.has_capability("open"):
            buttons.append(
                RingDoorButton(config_entry.entry_id, device, BUTTON_DESCRIPTION)
            )

    async_add_entities(buttons)


class RingDoorButton(RingEntityMixin, ButtonEntity):
    """Creates a button to open the ring intercom door."""

    def __init__(self, config_entry_id, device, description) -> None:
        """Initialize the button."""
        super().__init__(config_entry_id, device)
        self.entity_description = description
        self._extra = None
        self._attr_name = f"{device.name} {description.name}"
        self._attr_unique_id = f"{device.id}-{description.key}"

    def press(self) -> None:
        """Open the door."""
        self._device.open_door()
