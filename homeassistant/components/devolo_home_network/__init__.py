"""The devolo Home Network integration."""
from __future__ import annotations

import logging
from typing import Any

import async_timeout
from devolo_plc_api import Device
from devolo_plc_api.device_api import (
    ConnectedStationInfo,
    NeighborAPInfo,
    WifiGuestAccessGet,
)
from devolo_plc_api.exceptions.device import (
    DeviceNotFound,
    DevicePasswordProtected,
    DeviceUnavailable,
)
from devolo_plc_api.plcnet_api import LogicalNetwork

from homeassistant.components import zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
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
    SWITCH_GUEST_WIFI,
    SWITCH_LEDS,
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
        device.password = entry.data.get(
            CONF_PASSWORD, ""  # This key was added in HA Core 2022.6
        )
    except DeviceNotFound as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to {entry.data[CONF_IP_ADDRESS]}"
        ) from err

    async def async_update_connected_plc_devices() -> LogicalNetwork:
        """Fetch data from API endpoint."""
        assert device.plcnet
        try:
            async with async_timeout.timeout(10):
                return await device.plcnet.async_get_network_overview()
        except DeviceUnavailable as err:
            raise UpdateFailed(err) from err

    async def async_update_guest_wifi_status() -> WifiGuestAccessGet:
        """Fetch data from API endpoint."""
        assert device.device
        try:
            async with async_timeout.timeout(10):
                return await device.device.async_get_wifi_guest_access()
        except DeviceUnavailable as err:
            raise UpdateFailed(err) from err
        except DevicePasswordProtected as err:
            raise ConfigEntryAuthFailed(err) from err

    async def async_update_led_status() -> bool:
        """Fetch data from API endpoint."""
        assert device.device
        try:
            async with async_timeout.timeout(10):
                return await device.device.async_get_led_setting()
        except DeviceUnavailable as err:
            raise UpdateFailed(err) from err

    async def async_update_wifi_connected_station() -> list[ConnectedStationInfo]:
        """Fetch data from API endpoint."""
        assert device.device
        try:
            async with async_timeout.timeout(10):
                return await device.device.async_get_wifi_connected_station()
        except DeviceUnavailable as err:
            raise UpdateFailed(err) from err

    async def async_update_wifi_neighbor_access_points() -> list[NeighborAPInfo]:
        """Fetch data from API endpoint."""
        assert device.device
        try:
            async with async_timeout.timeout(30):
                return await device.device.async_get_wifi_neighbor_access_points()
        except DeviceUnavailable as err:
            raise UpdateFailed(err) from err

    async def disconnect(event: Event) -> None:
        """Disconnect from device."""
        await device.async_disconnect()

    coordinators: dict[str, DataUpdateCoordinator[Any]] = {}
    if device.plcnet:
        coordinators[CONNECTED_PLC_DEVICES] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=CONNECTED_PLC_DEVICES,
            update_method=async_update_connected_plc_devices,
            update_interval=LONG_UPDATE_INTERVAL,
        )
    if device.device and "led" in device.device.features:
        coordinators[SWITCH_LEDS] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=SWITCH_LEDS,
            update_method=async_update_led_status,
            update_interval=SHORT_UPDATE_INTERVAL,
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
        coordinators[SWITCH_GUEST_WIFI] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=SWITCH_GUEST_WIFI,
            update_method=async_update_guest_wifi_status,
            update_interval=SHORT_UPDATE_INTERVAL,
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
