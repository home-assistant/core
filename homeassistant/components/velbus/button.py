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
from homeassistant.exceptions import HomeAssistantError
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
    async_add_entities(VelbusButton(channel) for channel in cntrl.get_all("button"))


class VelbusButton(VelbusEntity, ButtonEntity):
    """Representation of a Velbus Binary Sensor."""

    _channel: VelbusaioButton | VelbusaioButtonCounter
    _attr_entity_registry_enabled_default = False
    _attr_entity_category = EntityCategory.CONFIG

    async def async_press(self) -> None:
        """Handle the button press."""
        try:
            await self._channel.press()
        except OSError as err:
            raise HomeAssistantError("Transmit for the press packet failed") from err
