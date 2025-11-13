"""Support for VELUX KLF 200 gateway button."""

from __future__ import annotations

from pyvlx import PyVLX, PyVLXException

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VeluxConfigEntry
from .const import DOMAIN

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VeluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button entities for the Velux integration."""
    async_add_entities(
        [VeluxGatewayRebootButton(config_entry.entry_id, config_entry.runtime_data)]
    )


class VeluxGatewayRebootButton(ButtonEntity):
    """Representation of the Velux Gateway reboot button."""

    _attr_has_entity_name = True
    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, config_entry_id: str, pyvlx: PyVLX) -> None:
        """Initialize the gateway reboot button."""
        self.pyvlx = pyvlx
        self._attr_unique_id = f"{config_entry_id}_reboot-gateway"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"gateway_{config_entry_id}")},
        )

    async def async_press(self) -> None:
        """Handle the button press - reboot the gateway."""
        try:
            await self.pyvlx.reboot_gateway()
        except PyVLXException as ex:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="reboot_failed",
            ) from ex
