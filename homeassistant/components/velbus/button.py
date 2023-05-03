"""Support for Velbus Buttons."""
from __future__ import annotations

from velbusaio.channels import (
    Button as VelbusaioButton,
    ButtonCounter as VelbusaioButtonCounter,
)

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .entity import VelbusEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Velbus switch based on config_entry."""
    await hass.data[DOMAIN][entry.entry_id]["tsk"]
    cntrl = hass.data[DOMAIN][entry.entry_id]["cntrl"]
    entities = []
    for channel in cntrl.get_all("button"):
        entities.append(VelbusButton(channel))
    async_add_entities(entities)


class VelbusButton(VelbusEntity, ButtonEntity):
    """Representation of a Velbus Binary Sensor."""

    _channel: VelbusaioButton | VelbusaioButtonCounter
    _attr_entity_registry_enabled_default = False
    _attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Handle the button press."""
        await self._channel.press()
