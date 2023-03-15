"""Obihai button module."""

from __future__ import annotations

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_platform

from .connectivity import ObihaiConnection
from .const import DOMAIN
from .entity import ObihaiEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: entity_platform.AddEntitiesCallback,
) -> None:
    """Set up the Obihai sensor entries."""
    requester: ObihaiConnection = hass.data[DOMAIN][entry.entry_id]

    await hass.async_add_executor_job(requester.update)
    buttons = [ObihaiButton(requester, "Reboot")]
    async_add_entities(buttons, update_before_add=True)


class ObihaiButton(ObihaiEntity, ButtonEntity):
    """Obihai Reboot button."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def press(self) -> None:
        """Press button."""

        if not self._pyobihai.call_reboot():
            raise HomeAssistantError("Reboot failed!")
