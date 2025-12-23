"""Support for WLED."""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import SOURCE_IGNORE
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .coordinator import (
    WLEDConfigEntry,
    WLEDDataUpdateCoordinator,
    WLEDReleasesDataUpdateCoordinator,
    normalize_mac_address,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = (
    Platform.BUTTON,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.UPDATE,
)

WLED_KEY: HassKey[WLEDReleasesDataUpdateCoordinator] = HassKey(DOMAIN)
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the WLED integration.

    We set up a single coordinator for fetching WLED releases, which
    is used across all WLED devices (and config entries) to avoid
    fetching the same data multiple times for each.
    """
    hass.data[WLED_KEY] = WLEDReleasesDataUpdateCoordinator(hass)
    await hass.data[WLED_KEY].async_request_refresh()
    return True


async def async_setup_entry(hass: HomeAssistant, entry: WLEDConfigEntry) -> bool:
    """Set up WLED from a config entry."""
    entry.runtime_data = WLEDDataUpdateCoordinator(hass, entry=entry)
    await entry.runtime_data.async_config_entry_first_refresh()

    # Set up all platforms for this device/entry.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: WLEDConfigEntry) -> bool:
    """Unload WLED config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = entry.runtime_data

        # Ensure disconnected and cleanup stop sub
        await coordinator.wled.disconnect()
        if coordinator.unsub:
            coordinator.unsub()

    return unload_ok


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: WLEDConfigEntry
) -> bool:
    """Migrate old entry."""
    _LOGGER.debug(
        "Migrating configuration from version %s.%s",
        config_entry.version,
        config_entry.minor_version,
    )

    if config_entry.version > 1:
        # The user has downgraded from a future version
        return False

    if config_entry.version == 1:
        if config_entry.minor_version < 2:
            # 1.2: Normalize unique ID to be lowercase MAC address without separators.
            # This matches the format used by WLED firmware.
            if TYPE_CHECKING:
                assert config_entry.unique_id
            normalized_mac_address = normalize_mac_address(config_entry.unique_id)
            duplicate_entries = [
                entry
                for entry in hass.config_entries.async_entries(DOMAIN)
                if entry.unique_id
                and normalize_mac_address(entry.unique_id) == normalized_mac_address
            ]
            ignored_entries = [
                entry
                for entry in duplicate_entries
                if entry.entry_id != config_entry.entry_id
                and entry.source == SOURCE_IGNORE
            ]
            if ignored_entries:
                _LOGGER.info(
                    "Found %d ignored WLED config entries with the same MAC address, removing them",
                    len(ignored_entries),
                )
                await asyncio.gather(
                    *[
                        hass.config_entries.async_remove(entry.entry_id)
                        for entry in ignored_entries
                    ]
                )
            if len(duplicate_entries) - len(ignored_entries) > 1:
                _LOGGER.warning(
                    "Found multiple WLED config entries with the same MAC address, cannot migrate to version 1.2"
                )
                return False

            hass.config_entries.async_update_entry(
                config_entry,
                unique_id=normalized_mac_address,
                version=1,
                minor_version=2,
            )

    _LOGGER.debug(
        "Migration to configuration version %s.%s successful",
        config_entry.version,
        config_entry.minor_version,
    )

    return True
