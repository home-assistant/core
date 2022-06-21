"""The devolo Home Network integration."""
from __future__ import annotations

import logging
from typing import Any

import async_timeout
from devolo_plc_api.device import Device
from devolo_plc_api.exceptions.device import DeviceNotFound, DeviceUnavailable

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONNECTED_PLC_DEVICES,
    CONNECTED_WIFI_CLIENTS,
    DOMAIN,
    LONG_UPDATE_INTERVAL,
    NEIGHBORING_WIFI_NETWORKS,
    PLATFORMS,
    SHORT_UPDATE_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up devolo Home Network from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    zeroconf_instance = await zeroconf.async_get_async_instance(hass)
    async_client = get_async_client(hass)

    try:
        device = Device(
            ip=entry.data[CONF_IP_ADDRESS], zeroconf_instance=zeroconf_instance
        )
        await device.async_connect(session_instance=async_client)
    except DeviceNotFound as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to {entry.data[CONF_IP_ADDRESS]}"
        ) from err

    async def async_update_connected_plc_devices() -> dict[str, Any]:
        """Fetch data from API endpoint."""
        try:
            async with async_timeout.timeout(10):
                return await device.plcnet.async_get_network_overview()  # type: ignore[no-any-return, union-attr]
        except DeviceUnavailable as err:
            raise UpdateFailed(err) from err

    async def async_update_wifi_connected_station() -> dict[str, Any]:
        """Fetch data from API endpoint."""
        try:
            async with async_timeout.timeout(10):
                return await device.device.async_get_wifi_connected_station()  # type: ignore[no-any-return, union-attr]
        except DeviceUnavailable as err:
            raise UpdateFailed(err) from err

    async def async_update_wifi_neighbor_access_points() -> dict[str, Any]:
        """Fetch data from API endpoint."""
        try:
            async with async_timeout.timeout(30):
                return await device.device.async_get_wifi_neighbor_access_points()  # type: ignore[no-any-return, union-attr]
        except DeviceUnavailable as err:
            raise UpdateFailed(err) from err

    async def disconnect(event: Event) -> None:
        """Disconnect from device."""
        await device.async_disconnect()

    coordinators: dict[str, DataUpdateCoordinator] = {}
    if device.plcnet:
        coordinators[CONNECTED_PLC_DEVICES] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=CONNECTED_PLC_DEVICES,
            update_method=async_update_connected_plc_devices,
            update_interval=LONG_UPDATE_INTERVAL,
        )
    if device.device and "wifi1" in device.device.features:
        coordinators[CONNECTED_WIFI_CLIENTS] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=CONNECTED_WIFI_CLIENTS,
            update_method=async_update_wifi_connected_station,
            update_interval=SHORT_UPDATE_INTERVAL,
        )
        coordinators[NEIGHBORING_WIFI_NETWORKS] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=NEIGHBORING_WIFI_NETWORKS,
            update_method=async_update_wifi_neighbor_access_points,
            update_interval=LONG_UPDATE_INTERVAL,
        )

    hass.data[DOMAIN][entry.entry_id] = {"device": device, "coordinators": coordinators}

    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, disconnect)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await hass.data[DOMAIN][entry.entry_id]["device"].async_disconnect()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
