"""The Big Ass Fans integration."""

from __future__ import annotations

from asyncio import timeout

from aiobafi6 import Device, Service
from aiobafi6.discovery import PORT
from aiobafi6.exceptions import DeviceUUIDMismatchError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_IP_ADDRESS, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady

from .const import QUERY_INTERVAL, RUN_TIMEOUT

type BAFConfigEntry = ConfigEntry[Device]


PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.CLIMATE,
    Platform.FAN,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: BAFConfigEntry) -> bool:
    """Set up Big Ass Fans from a config entry."""
    ip_address = entry.data[CONF_IP_ADDRESS]

    service = Service(ip_addresses=[ip_address], uuid=entry.unique_id, port=PORT)
    device = Device(service, query_interval_seconds=QUERY_INTERVAL)
    run_future = device.async_run()

    try:
        async with timeout(RUN_TIMEOUT):
            await device.async_wait_available()
    except DeviceUUIDMismatchError as ex:
        raise ConfigEntryNotReady(
            f"Unexpected device found at {ip_address}; expected {entry.unique_id}, found {device.dns_sd_uuid}"
        ) from ex
    except TimeoutError as ex:
        run_future.cancel()
        raise ConfigEntryNotReady(f"Timed out connecting to {ip_address}") from ex

    @callback
    def _async_cancel_run() -> None:
        run_future.cancel()

    entry.runtime_data = device
    entry.async_on_unload(_async_cancel_run)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: BAFConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
