"""Refoss devices platform loader."""
from __future__ import annotations

from typing import Final

from refoss_ha.controller.device import BaseDevice
from refoss_ha.device_manager import RefossDeviceListener, RefossDeviceManager
from refoss_ha.exceptions import RefossSocketInitErr
from refoss_ha.socket_server import SocketServerProtocol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.dispatcher import dispatcher_send

from .const import DOMAIN, REFOSS_DISCOVERY_NEW, REFOSS_HA_SIGNAL_UPDATE_ENTITY
from .models import HomeAssistantRefossData
from .util import get_refoss_socket_server

PLATFORMS: Final = [
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Async setup  entry."""
    hass.data.setdefault(DOMAIN, {})

    device_ids: set[str] = set()
    try:
        socketserver: SocketServerProtocol = await get_refoss_socket_server(hass)
        device_manager = RefossDeviceManager(socket_server=socketserver)
        await device_manager.async_start_broadcast_msg()
    except RefossSocketInitErr as ex:
        raise ConfigEntryNotReady(ex) from ex

    listener = DeviceListener(hass, device_ids)
    device_manager.add_device_listener(listener)

    hass.data[DOMAIN][entry.entry_id] = HomeAssistantRefossData(
        device_listener=listener,
        device_manager=device_manager,
    )

    await cleanup_device_registry(hass, device_manager)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def cleanup_device_registry(
    hass: HomeAssistant, device_manager: RefossDeviceManager
) -> None:
    """Remove deleted device registry entry if there are no remaining entities."""
    device_registry = dr.async_get(hass)
    for dev_id, device_entry in list(device_registry.devices.items()):
        for item in device_entry.identifiers:
            if item[0] == DOMAIN and item[1] not in device_manager.base_device_map:
                device_registry.async_remove_device(dev_id)
                break


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unloading the refoss platforms."""
    unload = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload:
        hass_data: HomeAssistantRefossData = hass.data[DOMAIN][entry.entry_id]
        hass_data.device_manager.remove_device_listener(hass_data.device_listener)
        hass_data.device_manager.base_device_map.clear()
        for task in hass_data.device_manager.tasks:
            task.cancel()

        hass.data[DOMAIN].pop(entry.entry_id)
        if not hass.data[DOMAIN]:
            hass.data.pop(DOMAIN)
    return unload


class DeviceListener(RefossDeviceListener):
    """Device Update Listener."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_ids: set[str],
    ) -> None:
        """Init DeviceListener."""
        self._hass = hass
        self._device_ids = device_ids

    async def update_device(self, device: BaseDevice) -> None:
        """Update device status."""
        if device.uuid in self._device_ids:
            dispatcher_send(
                self._hass, f"{REFOSS_HA_SIGNAL_UPDATE_ENTITY}_{device.uuid}"
            )

    async def add_device(self, device: BaseDevice) -> None:
        """Add device."""
        await self.async_remove_device(device.uuid)

        self._device_ids.add(device.uuid)
        dispatcher_send(self._hass, REFOSS_DISCOVERY_NEW, [device.uuid])
        dispatcher_send(self._hass, f"{REFOSS_HA_SIGNAL_UPDATE_ENTITY}_{device.uuid}")

    @callback
    async def async_remove_device(self, device_id: str) -> None:
        """Remove device from Home Assistant."""
        device_registry = dr.async_get(self._hass)
        device_entry = device_registry.async_get_device(
            identifiers={(DOMAIN, device_id)}
        )
        if device_entry is not None:
            device_registry.async_remove_device(device_entry.id)
            self._device_ids.discard(device_id)
