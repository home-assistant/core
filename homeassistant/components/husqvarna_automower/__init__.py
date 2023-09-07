"""The Husqvarna Automower integration."""

import contextlib
import logging
from typing import cast

from homeassistant.components.application_credentials import DATA_STORAGE
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue

from .const import DOMAIN, PLATFORMS
from .coordinator import AutomowerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    hass.data.setdefault(DOMAIN, {})
    api_key = None
    ap_storage: dict = cast(dict, hass.data.get("application_credentials"))
    ap_storage_data: dict = ap_storage[DATA_STORAGE].__dict__["data"]
    for k in ap_storage_data:
        api_key = ap_storage_data[k]["client_id"]
    entry_dict = entry.as_dict()
    access_token = entry_dict["data"]["token"]
    scope = entry_dict["data"]["token"]["scope"]
    if "amc:api" not in scope:
        async_create_issue(
            hass,
            DOMAIN,
            "wrong_scope",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="wrong_scope",
        )
    coordinator = AutomowerDataUpdateCoordinator(
        hass,
        api_key,
        access_token,
        entry=entry,
    )
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle unload of an entry."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    with contextlib.suppress(Exception):
        await coordinator.session.close()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
