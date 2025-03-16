"""Platform for the Daikin smart AC."""

from __future__ import annotations

import datetime
import logging

from pyiotdevice import async_get_thing_info

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.device_registry import DeviceEntry

from .const import DOMAIN, POLL_INTERVAL
from .coordinator import DaikinConfigEntry, DaikinDataUpdateCoordinator, UpdateFailed

PLATFORMS = [Platform.CLIMATE]

_LOGGER = logging.getLogger(__name__)


def _raise_invalid_response(device_apn: str) -> None:
    """Raise an UpdateFailed exception indicating that the device is unavailable due to an invalid response.

    Args:
        device_apn (str): The APN of the device which is unavailable.

    """
    raise UpdateFailed(f"The device {device_apn} is unavailable: Invalid response")


async def async_setup_entry(hass: HomeAssistant, entry: DaikinConfigEntry) -> bool:
    """Set up config entry for Daikin smart AC."""
    _LOGGER.debug("Setting up config entry for %s", DOMAIN)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry.data

    # Ensure that required data exists.
    device_key = entry.data.get(CONF_API_KEY)
    ip_address = entry.data.get("host")
    device_apn = entry.data.get("device_apn")

    if device_key is None or ip_address is None or device_apn is None:
        _LOGGER.error("Missing required configuration data")
        return False

    try:
        # Fetch the device info
        status = await async_get_thing_info(ip_address, device_key, "acstatus")

        if not isinstance(status, dict):
            _raise_invalid_response(device_apn)

    except UpdateFailed as ex:
        _LOGGER.debug("Update failed for device %s: %s", device_apn, ex)
        raise ConfigEntryNotReady from ex

    except Exception as ex:
        _LOGGER.debug(
            "Unexpected error during update for device %s: %s", device_apn, ex
        )
        raise ConfigEntryNotReady from ex

    # Create the coordinator.
    # The update_method should be a callable that fetches device data.
    coordinator = DaikinDataUpdateCoordinator(
        hass,
        entry,
        device_apn=device_apn,
        update_method=lambda: async_get_thing_info(ip_address, device_key, "acstatus"),
        update_interval=datetime.timedelta(seconds=POLL_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    # Store the coordinator in runtime_data.
    entry.runtime_data = coordinator

    # Forward setup to the supported platforms.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: DaikinConfigEntry) -> bool:
    """Unload a config entry for Daikin smart AC."""
    _LOGGER.debug("Unloading %s config entry", DOMAIN)
    hass.data[DOMAIN].pop(entry.entry_id)
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_config_entry_device(
    hass: HomeAssistant, config_entry: DaikinConfigEntry, device_entry: DeviceEntry
) -> bool:
    """Remove a config entry from a device.

    Returns True if the config entry should be removed from the device,
    i.e., if none of the device entry's identifiers for this integration's
    DOMAIN are found in the runtime data (specifically, in coordinator.data)
    of the config entry.
    """
    return not any(
        identifier
        for identifier in device_entry.identifiers
        if identifier[0] == DOMAIN
        and identifier[1] in (config_entry.runtime_data.data or {})
    )
