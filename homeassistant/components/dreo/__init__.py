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
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_time_interval

from .coordinator import DreoDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

type DreoConfigEntry = ConfigEntry[DreoData]

PLATFORMS = [Platform.FAN]
SYNC_INTERVAL = timedelta(seconds=15)


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
    for device in config_entry.runtime_data.devices:
        await async_setup_device(hass, config_entry, device)

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    async def _async_sync_wrapper(now=None):
        """Wrap the device synchronization function and call it."""
        # Safety check
        if (
            hasattr(config_entry, "runtime_data")
            and config_entry.runtime_data is not None
        ):
            await async_discover_devices(hass, config_entry)
        else:
            _LOGGER.warning("Runtime data missing, skipping sync")

    # Register scheduled task with proper cleanup on unload
    config_entry.async_on_unload(
        async_track_time_interval(
            hass,
            _async_sync_wrapper,
            SYNC_INTERVAL,
        )
    )

    return True


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
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator
    config_entry.runtime_data.coordinators[device_id] = coordinator


async def async_discover_devices(
    hass: HomeAssistant, config_entry: DreoConfigEntry
) -> None:
    """Synchronize cloud devices with local devices."""

    try:
        # Get latest device list
        cloud_devices = await _fetch_cloud_devices(hass, config_entry)
        if cloud_devices is None:
            return

        # Identify changed devices
        cloud_device_ids, new_device_ids, removed_device_ids = _identify_device_changes(
            config_entry, cloud_devices
        )

        # Process device changes
        await _add_new_devices(hass, config_entry, cloud_devices, new_device_ids)
        _remove_old_devices(config_entry, removed_device_ids)

        # Clean up unused entities and devices
        await _clean_entity_registry(hass, config_entry, cloud_device_ids)
        if removed_device_ids:
            await _clean_device_registry(hass, config_entry, removed_device_ids)

        # Update device list
        config_entry.runtime_data.devices = cloud_devices

        # Reload platforms if new devices were added
        if new_device_ids:
            await _reload_platforms(hass, config_entry)

    except (HsCloudBusinessException, HsCloudException) as ex:
        _LOGGER.error("Error syncing devices with Dreo cloud: %s", ex)
    except ConnectionError as ex:
        _LOGGER.error("Connection error during device sync: %s", ex)
    except Exception:
        _LOGGER.exception("Unexpected error during device sync")


async def _fetch_cloud_devices(
    hass: HomeAssistant, config_entry: DreoConfigEntry
) -> list[dict[str, Any]] | None:
    """Fetch device list from Dreo cloud API."""

    client = config_entry.runtime_data.client
    try:
        return await hass.async_add_executor_job(client.get_devices)
    except Exception as ex:
        _LOGGER.error("Failed to fetch devices from Dreo API: %s", ex)
        raise


def _identify_device_changes(
    config_entry: DreoConfigEntry, cloud_devices: list[dict[str, Any]]
) -> tuple[set[str], set[str], set[str]]:
    """Identify which devices have been added or removed."""
    # Get current device IDs and cloud device IDs
    current_device_ids = set(config_entry.runtime_data.coordinators.keys())
    cloud_device_ids = {
        str(device.get("deviceSn", ""))
        for device in cloud_devices
        if device.get("deviceSn")
    }

    # Calculate new and removed devices
    new_device_ids = cloud_device_ids - current_device_ids
    removed_device_ids = current_device_ids - cloud_device_ids

    return cloud_device_ids, new_device_ids, removed_device_ids


async def _add_new_devices(
    hass: HomeAssistant,
    config_entry: DreoConfigEntry,
    cloud_devices: list[dict[str, Any]],
    new_device_ids: set[str],
) -> None:
    """Set up new devices discovered from cloud."""
    for device in cloud_devices:
        device_id = str(device.get("deviceSn", ""))
        if device_id in new_device_ids:
            _LOGGER.info("New device added: %s", device_id)
            await async_setup_device(hass, config_entry, device)


def _remove_old_devices(
    config_entry: DreoConfigEntry, removed_device_ids: set[str]
) -> None:
    """Remove devices that no longer exist in the cloud."""
    for device_id in removed_device_ids:
        if device_id in config_entry.runtime_data.coordinators:
            _LOGGER.info("Device removed: %s", device_id)
            del config_entry.runtime_data.coordinators[device_id]


async def _clean_entity_registry(
    hass: HomeAssistant, config_entry: DreoConfigEntry, cloud_device_ids: set[str]
) -> None:
    """Remove entities associated with removed devices."""
    entity_registry = er.async_get(hass)

    # Find and remove entities
    for entity in list(entity_registry.entities.values()):
        if entity.config_entry_id != config_entry.entry_id:
            continue

        # Extract device ID from unique_id
        unique_id = entity.unique_id
        device_id = unique_id.split("_")[0] if "_" in unique_id else unique_id

        if device_id not in cloud_device_ids:
            entity_registry.async_remove(entity.entity_id)


async def _clean_device_registry(
    hass: HomeAssistant, config_entry: DreoConfigEntry, removed_device_ids: set[str]
) -> None:
    """Remove device registry entries for removed devices."""
    device_registry = dr.async_get(hass)

    for removed_device_id in removed_device_ids:
        # Find matching devices in the device registry
        device_entries = [
            dev
            for dev in device_registry.devices.values()
            if dev.config_entries == {config_entry.entry_id}
            and any(ident[1] == removed_device_id for ident in dev.identifiers)
        ]

        # Remove found devices
        for device_entry in device_entries:
            device_registry.async_remove_device(device_entry.id)


async def _reload_platforms(hass: HomeAssistant, config_entry: DreoConfigEntry) -> None:
    """Reload platforms to register new devices."""
    try:
        # Unload and reload all platforms
        await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)
        await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    except Exception as ex:
        _LOGGER.error("Error reloading platforms: %s", ex)
        raise


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Reload the config entry."""
    await async_unload_entry(hass, config_entry)
    await async_setup_entry(hass, config_entry)
