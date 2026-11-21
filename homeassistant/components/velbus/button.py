"""Support for Velbus Buttons."""

from typing import override

from velbusaio.channels import (
    Button as VelbusaioButton,
    ButtonCounter as VelbusaioButtonCounter,
)

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VelbusConfigEntry
from .entity import VelbusEntity, api_call
from .entity_discovery import async_setup_platform_discovery, discover_button_entities

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Velbus button based on config_entry."""
    await async_setup_platform_discovery(
        hass, entry, async_add_entities, discover_button_entities, Platform.BUTTON
    )


class VelbusButton(VelbusEntity, ButtonEntity):
    """Representation of a Velbus Binary Sensor."""

    _channel: VelbusaioButton | VelbusaioButtonCounter
    _attr_entity_registry_enabled_default = False
    _attr_entity_category = EntityCategory.CONFIG

    @api_call
    @override
    async def async_press(self) -> None:
        """Handle the button press."""
        await self._channel.press()
