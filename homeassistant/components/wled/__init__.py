"""Support for WLED."""

from __future__ import annotations

import logging

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.typing import ConfigType
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .coordinator import (
    WLEDConfigEntry,
    WLEDDataUpdateCoordinator,
    WLEDReleasesDataUpdateCoordinator,
    normalize_mac_address,
)

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
UNIQUE_ID_COLLISION_TITLE_LIMIT = 5

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the WLED integration.

    We set up a single coordinator for fetching WLED releases, which
    is used across all WLED devices (and config entries) to avoid
    fetching the same data multiple times for each.
    """
    hass.data[WLED_KEY] = WLEDReleasesDataUpdateCoordinator(hass)
    await hass.data[WLED_KEY].async_request_refresh()
    return True


def _find_all_entries_with_duplicated_mac(
    hass: HomeAssistant, entry: WLEDConfigEntry
) -> list[WLEDConfigEntry]:
    """Find all WLED config entries with the same MAC address."""
    assert entry.unique_id

    normalized_mac = normalize_mac_address(entry.unique_id)
    return [
        entry
        for entry in hass.config_entries.async_entries(DOMAIN)
        if entry.unique_id and normalize_mac_address(entry.unique_id) == normalized_mac
    ]


def _handle_device_conflict(hass: HomeAssistant, entry: WLEDConfigEntry) -> None:
    assert entry.unique_id
    duplicated_entries = _find_all_entries_with_duplicated_mac(hass, entry)

    if len(duplicated_entries) > 1:
        _LOGGER.error(
            "Found %d WLED configuration entries with the same MAC address: %s",
            len(duplicated_entries),
            entry.unique_id,
        )
        titles = [f"'{entry.title}'" for entry in duplicated_entries]
        translation_placeholders = {
            "configure_url": f"/config/integrations/integration/{DOMAIN}",
            "unique_id": str(entry.unique_id),
        }
        if len(titles) <= UNIQUE_ID_COLLISION_TITLE_LIMIT:
            translation_key = "config_entry_unique_id_collision"
            translation_placeholders["titles"] = ", ".join(titles)
        else:
            translation_key = "config_entry_unique_id_collision_many"
            translation_placeholders["number_of_entries"] = str(len(titles))
            translation_placeholders["titles"] = ", ".join(
                titles[:UNIQUE_ID_COLLISION_TITLE_LIMIT]
            )
            translation_placeholders["title_limit"] = str(
                UNIQUE_ID_COLLISION_TITLE_LIMIT
            )
        ir.async_create_issue(
            hass,
            DOMAIN,
            f"device_conflict_{entry.entry_id}",
            is_fixable=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key=translation_key,
            translation_placeholders=translation_placeholders,
            data={"entry_id": entry.entry_id},
        )
    else:
        ir.async_delete_issue(hass, DOMAIN, f"device_conflict_{entry.entry_id}")
        if entry.unique_id != normalize_mac_address(entry.unique_id):
            hass.config_entries.async_update_entry(
                entry, unique_id=normalize_mac_address(entry.unique_id)
            )


async def async_setup_entry(hass: HomeAssistant, entry: WLEDConfigEntry) -> bool:
    """Set up WLED from a config entry."""
    _handle_device_conflict(hass, entry)

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
