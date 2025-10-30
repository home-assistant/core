"""Support for VELUX KLF 200 gateway button."""

from __future__ import annotations

from pyvlx import PyVLXException

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VeluxConfigEntry
from .const import DOMAIN, LOGGER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VeluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button entities for the Velux integration."""
    async_add_entities([VeluxGatewayRebootButton(config_entry)])


class VeluxGatewayRebootButton(ButtonEntity):
    """Representation of the Velux Gateway reboot button."""

    _attr_has_entity_name = True
    _attr_translation_key = "reboot_gateway"
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, config_entry: VeluxConfigEntry) -> None:
        """Initialize the gateway reboot button."""
        self.pyvlx = config_entry.runtime_data
        self._attr_unique_id = f"{config_entry.entry_id}_reboot_gateway"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, f"gateway_{config_entry.entry_id}")},
        }

    async def async_press(self) -> None:
        """Handle the button press - reboot the gateway."""
        try:
            await self.pyvlx.reboot_gateway()
        except PyVLXException as ex:
            LOGGER.error("Failed to reboot gateway: %s", ex)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="reboot_failed",
            ) from ex
