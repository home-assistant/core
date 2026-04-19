"""Wibeee Energy Monitor integration for Home Assistant.

This integration communicates with Wibeee (formerly Mirubee) energy monitoring
devices manufactured by Smilics/Circutor over the local network.

Supports two update modes:
- **Local Push** (default): The WiBeee pushes data to HA's built-in HTTP
  server (port 8123 by default) at ``/Wibeee/receiverAvg``.
  Can auto-configure the device to point to the HA instance.
- **Polling**: Periodically fetches status.xml from the device.

No HACS required - included as a built-in Home Assistant integration.

Documentation: https://github.com/fquinto/pywibeee
Device info: http://wibeee.circutor.com/
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging

import aiohttp
from pywibeee import WibeeeAPI, WibeeeDeviceInfo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_MAC_ADDRESS,
    CONF_SCAN_INTERVAL,
    CONF_UPDATE_MODE,
    CONF_WIBEEE_ID,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,  # noqa: F401 — re-exported for other modules
    MODE_LOCAL_PUSH,
    MODE_POLLING,
)
from .coordinator import WibeeeCoordinator
from .push_receiver import async_setup_push_receiver

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BUTTON, Platform.SENSOR]


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
    except Exception as err:
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
        scan_interval = timedelta(
            seconds=entry.options.get(
                CONF_SCAN_INTERVAL,
                int(DEFAULT_SCAN_INTERVAL.total_seconds()),
            )
        )
        coordinator = WibeeeCoordinator(
            hass,
            api,
            name=f"Wibeee {device_info.mac_addr_short}",
            update_interval=scan_interval,
        )
        await coordinator.async_config_entry_first_refresh()
    else:
        # Push mode: no polling, data arrives via async_set_updated_data()
        coordinator = WibeeeCoordinator(
            hass,
            api,
            name=f"Wibeee {device_info.mac_addr_short}",
            update_interval=None,
        )
        # Do one initial poll to discover available sensors
        try:
            initial_data = await api.async_fetch_sensors_data(retries=3)
        except (TimeoutError, aiohttp.ClientError) as err:
            raise ConfigEntryNotReady(f"Error connecting to Wibeee at {host}") from err

        if not initial_data:
            raise ConfigEntryNotReady(
                f"Could not fetch initial sensor data from Wibeee at {host}"
            )

        coordinator.async_push_update(initial_data)
        # Register with push receiver
        receiver = async_setup_push_receiver(hass)
        receiver.register_device(mac_addr, coordinator.async_push_update)

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
