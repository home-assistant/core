"""The Marstek integration."""

from __future__ import annotations

import logging
from typing import Any

from pymarstek import MarstekUDPClient, get_es_mode

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.device_registry import format_mac
from homeassistant.helpers.typing import ConfigType

from .const import DEFAULT_UDP_PORT, DOMAIN, PLATFORMS
from .coordinator import MarstekDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

type MarstekConfigEntry = ConfigEntry[
    tuple[MarstekUDPClient, MarstekDataUpdateCoordinator, dict[str, Any]]
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Marstek component."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> bool:
    """Set up Marstek from a config entry."""
    _LOGGER.info("Setting up Marstek config entry: %s", entry.title)

    udp_client = MarstekUDPClient()
    await udp_client.async_setup()

    stored_ip = entry.data[CONF_HOST]
    stored_mac = (
        entry.data.get("ble_mac") or entry.data.get("mac") or entry.data.get("wifi_mac")
    )

    # Fetch device information from device, not from config_entry (mik-laj feedback)
    # This ensures we have the latest device information, especially if IP has changed
    device_info: dict[str, Any] | None = None
    try:
        # Try to connect with stored IP first
        await udp_client.send_request(
            get_es_mode(0),
            stored_ip,
            DEFAULT_UDP_PORT,
            timeout=2.0,
        )
        # Connection successful, but verify IP hasn't changed
        # Always do a fresh discovery to ensure we have the latest IP
        _LOGGER.debug("Connection successful, verifying device IP via discovery")
        devices = await udp_client.discover_devices(use_cache=False)
        _LOGGER.debug("Discovery found %d device(s)", len(devices))

        # Find device by MAC address (most reliable)
        if stored_mac:
            for device in devices:
                device_mac = (
                    device.get("ble_mac") or device.get("mac") or device.get("wifi_mac")
                )
                if device_mac and format_mac(device_mac) == format_mac(stored_mac):
                    device_info = device
                    device_ip = device.get("ip", stored_ip)
                    if device_ip != stored_ip:
                        _LOGGER.info(
                            "Device IP changed from %s to %s (detected during setup)",
                            stored_ip,
                            device_ip,
                        )
                    break

        # If not found by MAC, try by IP (device might be at stored IP)
        if not device_info:
            for device in devices:
                if device.get("ip") == stored_ip:
                    device_info = device
                    _LOGGER.debug("Found device at stored IP: %s", stored_ip)
                    break

        # If device_info still not found, use config_entry data as fallback
        # This should be rare since we just connected successfully
        if not device_info:
            _LOGGER.warning(
                "Device not found in discovery results, using config_entry data. "
                "This might indicate IP has changed but device not responding to discovery"
            )
            device_info = {
                "ip": stored_ip,
                "mac": entry.data.get("mac", ""),
                "device_type": entry.data.get("device_type", "Unknown"),
                "version": entry.data.get("version", 0),
                "wifi_name": entry.data.get("wifi_name", ""),
                "wifi_mac": entry.data.get("wifi_mac", ""),
                "ble_mac": entry.data.get("ble_mac", ""),
            }
    except (TimeoutError, OSError, ValueError):
        # Connection failed, try to rediscover device (mik-laj feedback)
        # This is the only case where we need to broadcast
        _LOGGER.info(
            "Connection to device at %s failed, attempting to rediscover via UDP broadcast",
            stored_ip,
        )
        devices = await udp_client.discover_devices(use_cache=False)
        _LOGGER.info("UDP broadcast discovery found %d device(s)", len(devices))

        # Find device by MAC address
        if stored_mac:
            _LOGGER.debug("Searching for device with MAC: %s", stored_mac)
            for device in devices:
                device_mac = (
                    device.get("ble_mac") or device.get("mac") or device.get("wifi_mac")
                )
                if device_mac and format_mac(device_mac) == format_mac(stored_mac):
                    _LOGGER.info(
                        "Found device by MAC %s at new IP: %s",
                        stored_mac,
                        device.get("ip"),
                    )
                    device_info = device
                    break

        if not device_info:
            _LOGGER.error(
                "Unable to find device with MAC %s after broadcast discovery",
                stored_mac or "unknown",
            )
            await udp_client.async_cleanup()
            raise ConfigEntryNotReady("Unable to find device after IP change") from None

    if not device_info:
        await udp_client.async_cleanup()
        raise ConfigEntryNotReady("Unable to get device information") from None

    # Check if IP has changed and update config entry (mik-laj feedback)
    current_ip = device_info.get("ip", stored_ip)
    if current_ip != stored_ip:
        _LOGGER.info(
            "Device IP changed from %s to %s, updating config entry",
            stored_ip,
            current_ip,
        )
        hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, CONF_HOST: current_ip},
        )

    # Build device info dict
    device_info_dict = {
        "ip": current_ip,
        "mac": device_info.get("mac", ""),
        "device_type": device_info.get(
            "device_type", entry.data.get("device_type", "Unknown")
        ),
        "version": device_info.get("version", entry.data.get("version", 0)),
        "wifi_name": device_info.get("wifi_name", entry.data.get("wifi_name", "")),
        "wifi_mac": device_info.get("wifi_mac", entry.data.get("wifi_mac", "")),
        "ble_mac": device_info.get("ble_mac", entry.data.get("ble_mac", "")),
    }

    # Create coordinator in __init__.py (mik-laj feedback)
    coordinator = MarstekDataUpdateCoordinator(
        hass, entry, udp_client, device_info_dict["ip"]
    )
    await coordinator.async_config_entry_first_refresh()

    # Store client, coordinator, and device_info in runtime_data
    entry.runtime_data = (udp_client, coordinator, device_info_dict)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Marstek config entry: %s", entry.title)

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok and entry.runtime_data:
        udp_client, _, _ = entry.runtime_data
        await udp_client.async_cleanup()

    return unload_ok
