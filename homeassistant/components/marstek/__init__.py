"""The Marstek integration."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

from pymarstek import MarstekUDPClient, get_es_mode

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_UDP_PORT, DOMAIN, PLATFORMS
from .coordinator import MarstekDataUpdateCoordinator
from .scanner import MarstekScanner

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


@dataclass
class MarstekRuntimeData:
    """Runtime data for Marstek integration."""

    udp_client: MarstekUDPClient
    coordinator: MarstekDataUpdateCoordinator
    device_info: dict[str, Any]


type MarstekConfigEntry = ConfigEntry[MarstekRuntimeData]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Marstek component."""
    # Initialize scanner (only once, regardless of number of config entries)
    # Scanner will detect IP changes and update config entries via config flow
    scanner = MarstekScanner.async_get(hass)
    await scanner.async_setup()
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> bool:
    """Set up Marstek from a config entry."""
    _LOGGER.info("Setting up Marstek config entry: %s", entry.title)

    udp_client = MarstekUDPClient()
    await udp_client.async_setup()

    stored_ip = entry.data[CONF_HOST]
    # Only use BLE-MAC for device identification (user feedback)
    stored_ble_mac = entry.data.get("ble_mac")

    _LOGGER.info(
        "Starting setup: attempting to connect to device at IP %s (BLE-MAC: %s)",
        stored_ip,
        stored_ble_mac or "unknown",
    )

    # Try to connect with stored IP (mik-laj feedback)
    # If we have an IP address in the configuration, we should always connect to that IP
    # Discovery is handled by Scanner, not here
    try:
        _LOGGER.info("Attempting connection to %s:%s", stored_ip, DEFAULT_UDP_PORT)
        await udp_client.send_request(
            get_es_mode(0),
            stored_ip,
            DEFAULT_UDP_PORT,
            timeout=5.0,  # Increased timeout for initial connection
        )
        # Connection successful - device is at the configured IP
        # Use device info from config_entry (saved during config flow)
        _LOGGER.info(
            "Connection successful to device at %s - using config_entry data",
            stored_ip,
        )
    except (TimeoutError, OSError, ValueError) as ex:
        # Connection failed - device IP may have changed
        # Scanner will detect IP changes and update config entry via config flow
        # Raise ConfigEntryNotReady to allow Home Assistant to retry after Scanner updates IP
        await udp_client.async_cleanup()
        _LOGGER.warning(
            "Unable to connect to device at %s (error: %s: %s). "
            "Scanner will detect IP changes automatically",
            stored_ip,
            type(ex).__name__,
            str(ex),
        )
        raise ConfigEntryNotReady(
            f"Unable to connect to device at {stored_ip}. "
            "Scanner will detect IP changes and update configuration automatically."
        ) from ex

    # Use device info from config_entry (saved during config flow)
    device_info_dict = {
        "ip": stored_ip,
        "mac": entry.data.get("mac", ""),
        "device_type": entry.data.get("device_type", "Unknown"),
        "version": entry.data.get("version", 0),
        "wifi_name": entry.data.get("wifi_name", ""),
        "wifi_mac": entry.data.get("wifi_mac", ""),
        "ble_mac": entry.data.get("ble_mac", ""),
    }

    # Create coordinator in __init__.py (mik-laj feedback)
    coordinator = MarstekDataUpdateCoordinator(
        hass, entry, udp_client, device_info_dict["ip"]
    )
    await coordinator.async_config_entry_first_refresh()

    # Store client, coordinator, and device_info in runtime_data
    entry.runtime_data = MarstekRuntimeData(
        udp_client=udp_client,
        coordinator=coordinator,
        device_info=device_info_dict,
    )

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Marstek config entry: %s", entry.title)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.runtime_data:
        await entry.runtime_data.udp_client.async_cleanup()

    return unload_ok
