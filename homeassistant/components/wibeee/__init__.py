"""The Wibeee integration."""

from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import logging
import socket
from xml.etree.ElementTree import ParseError as XMLParseError

import aiohttp
from pywibeee import WibeeeAPI, WibeeeDeviceInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_MAC_ADDRESS,
    CONF_UPDATE_MODE,
    CONF_WIBEEE_ID,
    DEFAULT_SCAN_INTERVAL,
    MODE_LOCAL_PUSH,
    MODE_POLLING,
    PUSH_STALE_AFTER,
)
from .coordinator import WibeeeCoordinator
from .push_receiver import async_setup_push_receiver

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR]


@dataclass
class WibeeeRuntimeData:
    """Runtime data stored in entry.runtime_data."""

    api: WibeeeAPI
    device_info: WibeeeDeviceInfo
    coordinator: WibeeeCoordinator


WibeeeConfigEntry = ConfigEntry[WibeeeRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: WibeeeConfigEntry) -> bool:
    """Set up Wibeee from a config entry."""
    mode = entry.options.get(CONF_UPDATE_MODE, MODE_LOCAL_PUSH)
    host = entry.data[CONF_HOST]
    mac_addr = entry.data[CONF_MAC_ADDRESS]
    wibeee_id = entry.data.get(CONF_WIBEEE_ID, "WIBEEE")

    _LOGGER.debug(
        "Setting up Wibeee entry %s (mode=%s, host=%s)",
        entry.entry_id,
        mode,
        host,
    )

    session = async_get_clientsession(hass)
    api = WibeeeAPI(session, host)

    # Fetch device info
    try:
        device_info = await api.async_fetch_device_info(retries=3)
    except (TimeoutError, aiohttp.ClientError) as err:
        raise ConfigEntryNotReady(f"Could not connect to Wibeee at {host}") from err

    if device_info is None:
        _LOGGER.warning("Could not get device info from %s, using fallback", host)
        device_info = WibeeeDeviceInfo(
            wibeee_id=wibeee_id,
            mac_addr=mac_addr,
            model="Unknown",
            firmware_version="Unknown",
            ip_addr=host,
        )

    # Create coordinator based on mode
    if mode == MODE_POLLING:
        coordinator = WibeeeCoordinator(
            hass,
            api,
            config_entry=entry,
            name=f"Wibeee {device_info.mac_addr_short}",
            update_interval=DEFAULT_SCAN_INTERVAL,
        )
        await coordinator.async_config_entry_first_refresh()
    else:
        # Push mode: no polling, data arrives via async_set_updated_data()
        coordinator = WibeeeCoordinator(
            hass,
            api,
            config_entry=entry,
            name=f"Wibeee {device_info.mac_addr_short}",
            update_interval=None,
            stale_after=PUSH_STALE_AFTER,
        )
        # Do one initial poll to discover available sensors
        try:
            initial_data = await api.async_fetch_sensors_data(retries=3)
        except (TimeoutError, aiohttp.ClientError, XMLParseError) as err:
            raise ConfigEntryNotReady(f"Error connecting to Wibeee at {host}") from err

        if not initial_data or not isinstance(initial_data, dict):
            raise ConfigEntryNotReady(
                f"Could not fetch initial sensor data from Wibeee at {host}"
            )

        # Seed the coordinator with the bootstrap data and arm the
        # push staleness watchdog.
        coordinator.async_push_update(initial_data)

        # Register with push receiver
        # Ensure we use a concrete IP even if host is a hostname for validation
        try:
            resolved_ip = str(ipaddress.ip_address(host))
        except ValueError:
            try:
                resolved_ip = await hass.async_add_executor_job(
                    socket.gethostbyname, host
                )
                resolved_ip = str(ipaddress.ip_address(resolved_ip))
            except (OSError, ValueError) as err:
                raise ConfigEntryNotReady(
                    f"Could not resolve Wibeee host {host} to an IP address for push mode"
                ) from err

        receiver = async_setup_push_receiver(hass)
        receiver.register_device(mac_addr, resolved_ip, coordinator.async_push_update)

        entry.async_on_unload(lambda: receiver.unregister_device(mac_addr))

    entry.runtime_data = WibeeeRuntimeData(
        api=api, device_info=device_info, coordinator=coordinator
    )

    # Reload on options change
    entry.async_on_unload(entry.add_update_listener(async_update_options))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WibeeeConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("Unloading Wibeee entry %s", entry.entry_id)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        del entry.runtime_data
    return unload_ok


async def async_update_options(hass: HomeAssistant, entry: WibeeeConfigEntry) -> None:
    """Handle options update - reload the entry."""
    await hass.config_entries.async_reload(entry.entry_id)
