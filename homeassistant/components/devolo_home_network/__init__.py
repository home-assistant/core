"""The devolo Home Network integration."""

from __future__ import annotations

import logging
from typing import Any

from devolo_plc_api import Device
from devolo_plc_api.device_api import (
    ConnectedStationInfo,
    NeighborAPInfo,
    UpdateFirmwareCheck,
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
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    CONNECTED_PLC_DEVICES,
    CONNECTED_WIFI_CLIENTS,
    DOMAIN,
    FIRMWARE_UPDATE_INTERVAL,
    LONG_UPDATE_INTERVAL,
    NEIGHBORING_WIFI_NETWORKS,
    REGULAR_FIRMWARE,
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
    device_registry = dr.async_get(hass)

    try:
        device = Device(
            ip=entry.data[CONF_IP_ADDRESS], zeroconf_instance=zeroconf_instance
        )
        await device.async_connect(session_instance=async_client)
        device.password = entry.data.get(
            CONF_PASSWORD,
            "",  # This key was added in HA Core 2022.6
        )
    except DeviceNotFound as err:
        raise ConfigEntryNotReady(
            f"Unable to connect to {entry.data[CONF_IP_ADDRESS]}",
            translation_domain=DOMAIN,
            translation_key="connection_failed",
            translation_placeholders={"ip_address": entry.data[CONF_IP_ADDRESS]},
        ) from err

    hass.data[DOMAIN][entry.entry_id] = {"device": device}

    async def async_update_firmware_available() -> UpdateFirmwareCheck:
        """Fetch data from API endpoint."""
        assert device.device
        update_sw_version(device_registry, device)
        try:
            return await device.device.async_check_firmware_available()
        except DeviceUnavailable as err:
            raise UpdateFailed(err) from err

    async def async_update_connected_plc_devices() -> LogicalNetwork:
        """Fetch data from API endpoint."""
        assert device.plcnet
        update_sw_version(device_registry, device)
        try:
            return await device.plcnet.async_get_network_overview()
        except DeviceUnavailable as err:
            raise UpdateFailed(err) from err

    async def async_update_guest_wifi_status() -> WifiGuestAccessGet:
        """Fetch data from API endpoint."""
        assert device.device
        update_sw_version(device_registry, device)
        try:
            return await device.device.async_get_wifi_guest_access()
        except DeviceUnavailable as err:
            raise UpdateFailed(err) from err
        except DevicePasswordProtected as err:
            raise ConfigEntryAuthFailed(
                err, translation_domain=DOMAIN, translation_key="password_wrong"
            ) from err

    async def async_update_led_status() -> bool:
        """Fetch data from API endpoint."""
        assert device.device
        update_sw_version(device_registry, device)
        try:
            return await device.device.async_get_led_setting()
        except DeviceUnavailable as err:
            raise UpdateFailed(err) from err

    async def async_update_wifi_connected_station() -> list[ConnectedStationInfo]:
        """Fetch data from API endpoint."""
        assert device.device
        update_sw_version(device_registry, device)
        try:
            return await device.device.async_get_wifi_connected_station()
        except DeviceUnavailable as err:
            raise UpdateFailed(err) from err

    async def async_update_wifi_neighbor_access_points() -> list[NeighborAPInfo]:
        """Fetch data from API endpoint."""
        assert device.device
        update_sw_version(device_registry, device)
        try:
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
    if device.device and "update" in device.device.features:
        coordinators[REGULAR_FIRMWARE] = DataUpdateCoordinator(
            hass,
            _LOGGER,
            name=REGULAR_FIRMWARE,
            update_method=async_update_firmware_available,
            update_interval=FIRMWARE_UPDATE_INTERVAL,
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

    for coordinator in coordinators.values():
        await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id]["coordinators"] = coordinators

    await hass.config_entries.async_forward_entry_setups(entry, platforms(device))

    entry.async_on_unload(
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, disconnect)
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    device: Device = hass.data[DOMAIN][entry.entry_id]["device"]
    unload_ok = await hass.config_entries.async_unload_platforms(
        entry, platforms(device)
    )
    if unload_ok:
        await device.async_disconnect()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


@callback
def platforms(device: Device) -> set[Platform]:
    """Assemble supported platforms."""
    supported_platforms = {Platform.BUTTON, Platform.SENSOR, Platform.SWITCH}
    if device.plcnet:
        supported_platforms.add(Platform.BINARY_SENSOR)
    if device.device and "wifi1" in device.device.features:
        supported_platforms.add(Platform.DEVICE_TRACKER)
        supported_platforms.add(Platform.IMAGE)
    if device.device and "update" in device.device.features:
        supported_platforms.add(Platform.UPDATE)
    return supported_platforms


@callback
def update_sw_version(device_registry: dr.DeviceRegistry, device: Device) -> None:
    """Update device registry with new firmware version."""
    if (
        device_entry := device_registry.async_get_device(
            identifiers={(DOMAIN, str(device.serial_number))}
        )
    ) and device_entry.sw_version != device.firmware_version:
        device_registry.async_update_device(
            device_id=device_entry.id, sw_version=device.firmware_version
        )
