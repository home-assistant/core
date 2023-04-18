"""UPnP/IGD integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta

import async_timeout
from async_upnp_client.exceptions import UpnpConnectionError

from homeassistant.components import ssdp
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr

from .const import (
    CONFIG_ENTRY_HOST,
    CONFIG_ENTRY_MAC_ADDRESS,
    CONFIG_ENTRY_ORIGINAL_UDN,
    CONFIG_ENTRY_ST,
    CONFIG_ENTRY_UDN,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    IDENTIFIER_HOST,
    IDENTIFIER_SERIAL_NUMBER,
    LOGGER,
)
from .coordinator import UpnpDataUpdateCoordinator
from .device import async_create_device

NOTIFICATION_ID = "upnp_notification"
NOTIFICATION_TITLE = "UPnP/IGD Setup"

PLATFORMS = [Platform.BINARY_SENSOR, Platform.SENSOR]

CONFIG_SCHEMA = cv.removed(DOMAIN, raise_if_present=False)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up UPnP/IGD device from a config entry."""
    LOGGER.debug("Setting up config entry: %s", entry.entry_id)

    hass.data.setdefault(DOMAIN, {})

    udn = entry.data[CONFIG_ENTRY_UDN]
    st = entry.data[CONFIG_ENTRY_ST]  # pylint: disable=invalid-name
    usn = f"{udn}::{st}"

    # Register device discovered-callback.
    device_discovered_event = asyncio.Event()
    discovery_info: ssdp.SsdpServiceInfo | None = None

    async def device_discovered(
        headers: ssdp.SsdpServiceInfo, change: ssdp.SsdpChange
    ) -> None:
        if change == ssdp.SsdpChange.BYEBYE:
            return

        nonlocal discovery_info
        LOGGER.debug("Device discovered: %s, at: %s", usn, headers.ssdp_location)
        discovery_info = headers
        device_discovered_event.set()

    cancel_discovered_callback = await ssdp.async_register_callback(
        hass,
        device_discovered,
        {
            "usn": usn,
        },
    )

    try:
        async with async_timeout.timeout(10):
            await device_discovered_event.wait()
    except asyncio.TimeoutError as err:
        raise ConfigEntryNotReady(f"Device not discovered: {usn}") from err
    finally:
        cancel_discovered_callback()

    # Create device.
    assert discovery_info is not None
    assert discovery_info.ssdp_location is not None
    location = discovery_info.ssdp_location
    try:
        device = await async_create_device(hass, location)
    except UpnpConnectionError as err:
        raise ConfigEntryNotReady(
            f"Error connecting to device at location: {location}, err: {err}"
        ) from err

    # Track the original UDN such that existing sensors do not change their unique_id.
    if CONFIG_ENTRY_ORIGINAL_UDN not in entry.data:
        hass.config_entries.async_update_entry(
            entry=entry,
            data={
                **entry.data,
                CONFIG_ENTRY_ORIGINAL_UDN: device.udn,
            },
        )
    device.original_udn = entry.data[CONFIG_ENTRY_ORIGINAL_UDN]

    # Store mac address for changed UDN matching.
    device_mac_address = await device.async_get_mac_address()
    if device_mac_address and not entry.data.get(CONFIG_ENTRY_MAC_ADDRESS):
        hass.config_entries.async_update_entry(
            entry=entry,
            data={
                **entry.data,
                CONFIG_ENTRY_MAC_ADDRESS: device_mac_address,
                CONFIG_ENTRY_HOST: device.host,
            },
        )

    identifiers = {(DOMAIN, device.usn)}
    if device.host:
        identifiers.add((IDENTIFIER_HOST, device.host))
    if device.serial_number:
        identifiers.add((IDENTIFIER_SERIAL_NUMBER, device.serial_number))

    connections = {(dr.CONNECTION_UPNP, device.udn)}
    if device_mac_address:
        connections.add((dr.CONNECTION_NETWORK_MAC, device_mac_address))

    dev_registry = dr.async_get(hass)
    device_entry = dev_registry.async_get_device(
        identifiers=identifiers, connections=connections
    )
    if device_entry:
        LOGGER.debug(
            "Found device using connections: %s, device_entry: %s",
            connections,
            device_entry,
        )
    if not device_entry:
        # No device found, create new device entry.
        device_entry = dev_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            connections=connections,
            identifiers=identifiers,
            name=device.name,
            manufacturer=device.manufacturer,
            model=device.model_name,
        )
        LOGGER.debug(
            "Created device using UDN '%s', device_entry: %s", device.udn, device_entry
        )
    else:
        # Update identifier.
        device_entry = dev_registry.async_update_device(
            device_entry.id,
            new_identifiers=identifiers,
        )

    assert device_entry
    update_interval = timedelta(seconds=DEFAULT_SCAN_INTERVAL)
    coordinator = UpnpDataUpdateCoordinator(
        hass,
        device=device,
        device_entry=device_entry,
        update_interval=update_interval,
    )

    # Try an initial refresh.
    await coordinator.async_config_entry_first_refresh()

    # Save coordinator.
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Setup platforms, creating sensors/binary_sensors.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a UPnP/IGD device from a config entry."""
    LOGGER.debug("Unloading config entry: %s", entry.entry_id)

    # Unload platforms.
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        del hass.data[DOMAIN][entry.entry_id]

    return unload_ok
