"""The Liebherr integration."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging

from pyliebherrhomeapi import LiebherrClient
from pyliebherrhomeapi.exceptions import (
    LiebherrAuthenticationError,
    LiebherrConnectionError,
)

from homeassistant.const import CONF_API_KEY, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.event import async_track_time_interval

from .const import DEVICE_SCAN_INTERVAL, DOMAIN
from .coordinator import LiebherrConfigEntry, LiebherrCoordinator, LiebherrData

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: LiebherrConfigEntry) -> bool:
    """Set up Liebherr from a config entry."""
    # Create shared API client
    client = LiebherrClient(
        api_key=entry.data[CONF_API_KEY],
        session=async_get_clientsession(hass),
    )

    # Fetch device list to create coordinators
    try:
        devices = await client.get_devices()
    except LiebherrAuthenticationError as err:
        raise ConfigEntryAuthFailed("Invalid API key") from err
    except LiebherrConnectionError as err:
        raise ConfigEntryNotReady(f"Failed to connect to Liebherr API: {err}") from err

    # Create a coordinator for each device (may be empty if no devices)
    data = LiebherrData(client=client)
    for device in devices:
        coordinator = LiebherrCoordinator(
            hass=hass,
            config_entry=entry,
            client=client,
            device_id=device.device_id,
        )
        data.coordinators[device.device_id] = coordinator

    await asyncio.gather(
        *(
            coordinator.async_config_entry_first_refresh()
            for coordinator in data.coordinators.values()
        )
    )

    # Store runtime data
    entry.runtime_data = data

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Schedule periodic scan for new devices
    async def _async_scan_for_new_devices(_now: datetime) -> None:
        """Scan for new devices added to the account."""
        try:
            devices = await client.get_devices()
        except LiebherrAuthenticationError, LiebherrConnectionError:
            _LOGGER.debug("Failed to scan for new devices")
            return
        except Exception:
            _LOGGER.exception("Unexpected error scanning for new devices")
            return

        # Remove stale devices no longer returned by the API
        current_device_ids = {device.device_id for device in devices}
        device_registry = dr.async_get(hass)
        for device_entry in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            device_ids = {
                identifier[1]
                for identifier in device_entry.identifiers
                if identifier[0] == DOMAIN
            }
            if device_ids - current_device_ids:
                # Shut down coordinator if one exists
                for device_id in device_ids:
                    if coordinator := data.coordinators.pop(device_id, None):
                        await coordinator.async_shutdown()
                device_registry.async_update_device(
                    device_id=device_entry.id,
                    remove_config_entry_id=entry.entry_id,
                )

        # Add new devices
        new_coordinators: list[LiebherrCoordinator] = []
        for device in devices:
            if device.device_id not in data.coordinators:
                coordinator = LiebherrCoordinator(
                    hass=hass,
                    config_entry=entry,
                    client=client,
                    device_id=device.device_id,
                )
                await coordinator.async_refresh()
                if not coordinator.last_update_success:
                    _LOGGER.debug("Failed to set up new device %s", device.device_id)
                    continue
                data.coordinators[device.device_id] = coordinator
                new_coordinators.append(coordinator)

        if new_coordinators:
            async_dispatcher_send(
                hass,
                f"{DOMAIN}_new_device_{entry.entry_id}",
                new_coordinators,
            )

    entry.async_on_unload(
        async_track_time_interval(
            hass, _async_scan_for_new_devices, DEVICE_SCAN_INTERVAL
        )
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LiebherrConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
