"""The Midea integration."""

from collections.abc import Mapping
from typing import Any

from midealocal.const import ProtocolVersion
from midealocal.device import MideaDevice
from midealocal.devices import device_selector
from midealocal.discover import discover

from homeassistant.const import (
    CONF_DEVICE_ID,
    CONF_IP_ADDRESS,
    CONF_MODEL,
    CONF_NAME,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_TOKEN,
    CONF_TYPE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import CONF_KEY, CONF_SUBTYPE, LOGGER
from .entity import MideaConfigEntry

_PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.HUMIDIFIER,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SWITCH,
]


def _create_device(data: Mapping[str, Any], ip_address: str) -> MideaDevice | None:
    """Create the device object for the given entry data and IP address."""
    return device_selector(
        data[CONF_NAME],
        data[CONF_DEVICE_ID],
        data[CONF_TYPE],
        ip_address,
        data[CONF_PORT],
        data[CONF_TOKEN],
        data[CONF_KEY],
        ProtocolVersion(data[CONF_PROTOCOL]),
        data[CONF_MODEL],
        data[CONF_SUBTYPE],
        "",
    )


def _connect(device: MideaDevice) -> bool:
    """Connect to the device, always closing the socket on failure.

    connect() swallows AuthException/SocketException internally and can
    leave the socket open even though it reports failure, so it must be
    closed explicitly here to avoid a ResourceWarning.
    """
    connected = device.connect(True)
    if not connected:
        device.close_socket()
    return connected


def _discover_current_ip(device_id: int) -> str | None:
    """Look up the device's current IP address via local discovery.

    Devices reply to the discovery broadcast with a persistent device_id
    regardless of their current IP, so this can find a device that has
    moved to a new DHCP-assigned address.
    """
    found = discover()
    device = found.get(device_id)
    return device[CONF_IP_ADDRESS] if device else None


async def async_setup_entry(hass: HomeAssistant, entry: MideaConfigEntry) -> bool:
    """Set up Midea from a config entry."""

    data: Mapping[str, Any] = entry.data
    device_id: int = data[CONF_DEVICE_ID]
    ip_address: str = data[CONF_IP_ADDRESS]

    device = await hass.async_add_executor_job(_create_device, data, ip_address)
    if device is None:
        raise ConfigEntryError("Unable to initialize device")

    connected = await hass.async_add_executor_job(_connect, device)
    if not connected:
        new_ip_address = await hass.async_add_executor_job(
            _discover_current_ip, device_id
        )
        if new_ip_address and new_ip_address != ip_address:
            LOGGER.debug(
                "Device %s moved from %s to %s, updating config entry",
                device_id,
                ip_address,
                new_ip_address,
            )
            data = {**data, CONF_IP_ADDRESS: new_ip_address}
            hass.config_entries.async_update_entry(entry, data=data)
            new_device = await hass.async_add_executor_job(
                _create_device, data, new_ip_address
            )
            if new_device is not None:
                device = new_device
                connected = await hass.async_add_executor_job(_connect, device)
        if not connected:
            raise ConfigEntryNotReady(f"Unable to connect to device {device_id}")

    # The library's reconnect loop keeps retrying with a growing backoff
    # (up to 600s) without checking for a stop request while sleeping, so
    # device.close() alone cannot guarantee the background thread exits
    # promptly when offline. Marking it a daemon thread ensures it can
    # never block Home Assistant shutdown as a zombie thread.
    device.daemon = True
    await hass.async_add_executor_job(device.open)
    entry.runtime_data = device

    async def _close_device() -> None:
        await hass.async_add_executor_job(device.close)

    entry.async_on_unload(_close_device)
    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MideaConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
