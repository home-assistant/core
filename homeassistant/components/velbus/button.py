"""Support for Velbus Buttons."""

from __future__ import annotations

from velbusaio.channels import (
    Button as VelbusaioButton,
    ButtonCounter as VelbusaioButtonCounter,
)

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VelbusConfigEntry
from .entity import VelbusEntity, api_call

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: VelbusConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Velbus switch based on config_entry."""
    await entry.runtime_data.scan_task
    async_add_entities(
        VelbusButton(channel)
        for channel in entry.runtime_data.controller.get_all_button()
    )


class VelbusButton(VelbusEntity, ButtonEntity):
    """Representation of a Velbus Binary Sensor."""

    _channel: VelbusaioButton | VelbusaioButtonCounter
    _attr_entity_registry_enabled_default = False
    _attr_entity_category = EntityCategory.CONFIG

    @api_call
    async def async_press(self) -> None:
        """Handle the button press."""
        await self._channel.press()
