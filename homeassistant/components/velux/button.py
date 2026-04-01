"""Support for VELUX KLF 200 gateway button."""

from __future__ import annotations

from pyvlx import Node, PyVLX, PyVLXException

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import VeluxConfigEntry
from .const import DOMAIN
from .entity import VeluxEntity, wrap_pyvlx_call_exceptions

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: VeluxConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up button entities for the Velux integration."""
    entities: list[ButtonEntity] = [
        VeluxGatewayRebootButton(config_entry.entry_id, config_entry.runtime_data)
    ]
    entities.extend(
        VeluxIdentifyButton(node, config_entry.entry_id)
        for node in config_entry.runtime_data.nodes
        if isinstance(node, Node)
    )
    async_add_entities(entities)


class VeluxIdentifyButton(VeluxEntity, ButtonEntity):
    """Representation of a Velux identify button."""

    _attr_device_class = ButtonDeviceClass.IDENTIFY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, node: Node, config_entry_id: str) -> None:
        """Initialize the Velux identify button."""
        super().__init__(node, config_entry_id)
        self._attr_unique_id = f"{self._attr_unique_id}_identify"

    @wrap_pyvlx_call_exceptions
    async def async_press(self) -> None:
        """Identify the physical device."""
        await self.node.wink()


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
