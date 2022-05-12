"""Support for Ubiquiti's UniFi Protect NVR."""
from __future__ import annotations

import logging

from pyunifiprotect.data.base import ProtectAdoptableDeviceModel

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICES_THAT_ADOPT, DOMAIN
from .data import ProtectData
from .entity import ProtectDeviceEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Discover devices on a UniFi Protect NVR."""
    data: ProtectData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            ProtectButton(
                data,
                device,
            )
            for device in data.get_by_types(DEVICES_THAT_ADOPT)
        ]
    )


class ProtectButton(ProtectDeviceEntity, ButtonEntity):
    """A Ubiquiti UniFi Protect Reboot button."""

    _attr_entity_registry_enabled_default = False
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(
        self,
        data: ProtectData,
        device: ProtectAdoptableDeviceModel,
    ) -> None:
        """Initialize an UniFi camera."""
        super().__init__(data, device)
        self._attr_name = f"{self.device.name} Reboot Device"

    async def async_press(self) -> None:
        """Press the button."""

        _LOGGER.debug("Rebooting %s with id %s", self.device.model, self.device.id)
        await self.device.reboot()
