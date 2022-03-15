"""The KDEConnect integration."""
from __future__ import annotations

from abc import ABC, abstractmethod
import logging
from typing import Generic, TypeVar, cast

from pykdeconnect.client import KdeConnectClient
from pykdeconnect.devices import KdeConnectDevice
from pykdeconnect.plugin import Plugin
from pykdeconnect.plugin_registry import PluginRegistry

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_ID, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DATA_KEY_CLIENT, DATA_KEY_DEVICES, DATA_KEY_STORAGE, DOMAIN
from .helpers import ensure_running
from .storage import HomeAssistantStorage

_LOGGER = logging.getLogger(__name__)


_P = TypeVar("_P", bound=Plugin)


PLATFORMS: list[Platform] = [
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up KDE Connect from a config entry."""
    await ensure_running(hass)

    client = cast(KdeConnectClient, hass.data[DOMAIN][DATA_KEY_CLIENT])
    storage = cast(HomeAssistantStorage, hass.data[DOMAIN][DATA_KEY_STORAGE])

    storage.add_device(entry)

    device_id = entry.data[CONF_DEVICE_ID]
    device = client.get_device(device_id)
    assert device is not None

    hass.data[DOMAIN][DATA_KEY_DEVICES][entry.entry_id] = device

    hass.config_entries.async_setup_platforms(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        del hass.data[DOMAIN][DATA_KEY_DEVICES][entry.entry_id]

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove a config entry."""
    client = cast(KdeConnectClient, hass.data[DOMAIN][DATA_KEY_CLIENT])
    storage = cast(HomeAssistantStorage, hass.data[DOMAIN][DATA_KEY_STORAGE])
    device_id = entry.data[CONF_DEVICE_ID]
    storage.remove_device_by_id(device_id)

    device = client.get_device(device_id)
    if device is not None and device.is_connected:
        device.unpair()


class KdeConnectEntity(RestoreEntity, ABC):
    """A base class for all KDE Connect Entities."""

    device: KdeConnectDevice

    def __init__(self, device: KdeConnectDevice) -> None:
        """Initialize the KDE Connect Entity."""
        self.device = device

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self.device.device_id)},
            name=self.device.device_name,
            manufacturer="KDE Connect",
        )

    async def async_added_to_hass(self) -> None:
        """Set up an entity after it has been added to hass."""
        if (state := await self.async_get_last_state()) is None:
            return

        self.restore_state(state)

    @abstractmethod
    def restore_state(self, state: State) -> None:
        """Restore the state of the device on restart."""


class KdeConnectPluginEntity(KdeConnectEntity, Generic[_P], ABC):
    """A KDE Connect entity that uses a KDE Connect plugin."""

    plugin: _P

    def __init__(
        self,
        device: KdeConnectDevice,
        plugin_registry: PluginRegistry,
        plugin_class: type[_P],
    ) -> None:
        """Initialize the KDE Connect Plugin Entity."""
        super().__init__(device)
        self.plugin = plugin_registry.get_plugin(device, plugin_class)
