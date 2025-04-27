"""Dreo for Integration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from hscloud.hscloud import HsCloud
from hscloud.hscloudexception import HsCloudBusinessException, HsCloudException

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.event import async_track_time_interval

from .coordinator import DreoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

type DreoConfigEntry = ConfigEntry[DreoData]

PLATFORMS = [Platform.FAN]
SYNC_INTERVAL = timedelta(seconds=30)  # Device synchronization interval


@dataclass
class DreoData:
    """Dreo Data."""

    client: HsCloud
    devices: list[dict[str, Any]]
    coordinators: dict[str, DreoDataUpdateCoordinator]


async def async_login(hass: HomeAssistant, username: str, password: str) -> DreoData:
    """Log into Dreo and return client and device data."""
    client = HsCloud(username, password)

    def setup_client():
        client.login()
        return client.get_devices()

    try:
        devices = await hass.async_add_executor_job(setup_client)
    except HsCloudBusinessException as ex:
        raise ConfigEntryNotReady("invalid username or password") from ex

    return DreoData(client, devices, {})


async def async_setup_entry(hass: HomeAssistant, config_entry: DreoConfigEntry) -> bool:
    """Set up Dreo from as config entry."""
    username = config_entry.data[CONF_USERNAME]
    password = config_entry.data[CONF_PASSWORD]

    # Login and get device data
    config_entry.runtime_data = await async_login(hass, username, password)

    # Set up coordinators for each device
    await async_setup_devices(hass, config_entry)

    # Set up periodic device synchronization task - fixed to be thread-safe
    async def _async_sync_wrapper(now=None):
        """Wrap the device synchronization function and call it."""
        await async_sync_devices(hass, config_entry)

    async_track_time_interval(
        hass,
        _async_sync_wrapper,
        SYNC_INTERVAL,
    )

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    return True


async def async_setup_devices(
    hass: HomeAssistant, config_entry: DreoConfigEntry
) -> None:
    """Set up coordinators for all devices."""
    for device in config_entry.runtime_data.devices:
        await async_setup_device(hass, config_entry, device)


async def async_setup_device(
    hass: HomeAssistant, config_entry: DreoConfigEntry, device: dict[str, Any]
) -> None:
    """Set up coordinator for a single device."""
    device_model = device.get("model")
    device_id = str(device.get("deviceSn", ""))

    if not device_id:
        return

    # Skip if device already has a coordinator
    if device_id in config_entry.runtime_data.coordinators:
        return

    # Create device coordinator
    coordinator = DreoDataUpdateCoordinator(
        hass, config_entry.runtime_data.client, device_id, device_model or ""
    )

    # Initial data refresh
    try:
        await coordinator.async_config_entry_first_refresh()
    except HsCloudException as ex:
        _LOGGER.error("Failed to refresh device %s due to API error: %s", device_id, ex)
        return
    except ConnectionError as ex:
        _LOGGER.error("Failed to connect to device %s: %s", device_id, ex)
        return

    # Store coordinator
    config_entry.runtime_data.coordinators[device_id] = coordinator
    _LOGGER.debug("Setup coordinator for device %s", device_id)


async def async_sync_devices(
    hass: HomeAssistant, config_entry: DreoConfigEntry
) -> None:
    """Synchronize cloud devices with local devices."""
    _LOGGER.debug("Syncing devices from Dreo cloud")

    try:
        # Get latest device list
        username = config_entry.data[CONF_USERNAME]
        password = config_entry.data[CONF_PASSWORD]
        client = HsCloud(username, password)

        def get_cloud_devices():
            client.login()
            return client.get_devices()

        cloud_devices = await hass.async_add_executor_job(get_cloud_devices)

        # Get current configured device IDs
        current_device_ids = set(config_entry.runtime_data.coordinators.keys())

        # Process new devices
        for device in cloud_devices:
            device_id = str(device.get("deviceSn", ""))
            if not device_id:
                continue

            if device_id not in current_device_ids:
                _LOGGER.info("Found new device: %s", device_id)
                await async_setup_device(hass, config_entry, device)
                # Add to device list so platforms can create entities
                config_entry.runtime_data.devices.append(device)

        # Process removed devices
        cloud_device_ids = {
            str(device.get("deviceSn", ""))
            for device in cloud_devices
            if device.get("deviceSn")
        }
        removed_device_ids = current_device_ids - cloud_device_ids

        for device_id in removed_device_ids:
            _LOGGER.info("Device removed from cloud: %s", device_id)
            if device_id in config_entry.runtime_data.coordinators:
                # Mark coordinator as unavailable
                coordinator = config_entry.runtime_data.coordinators[device_id]
                coordinator.last_update_success = False
                await coordinator.async_request_refresh()
                # Remove from coordinator list
                del config_entry.runtime_data.coordinators[device_id]

        # Update device list
        config_entry.runtime_data.devices = cloud_devices

    except HsCloudBusinessException as ex:
        _LOGGER.error("Failed to sync devices due to business error: %s", ex)
    except HsCloudException as ex:
        _LOGGER.error("Failed to sync devices due to API error: %s", ex)
    except ConnectionError as ex:
        _LOGGER.error("Failed to connect to Dreo cloud: %s", ex)


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload the config entry."""
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)
