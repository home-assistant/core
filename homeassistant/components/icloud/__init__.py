"""The iCloud component."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .account import IcloudAccount
from .const import (
    CONF_GPS_ACCURACY_THRESHOLD,
    CONF_MAX_INTERVAL,
    CONF_WITH_FAMILY,
    DOMAIN,
    PLATFORMS,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .services import register_services


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an iCloud account from a config entry."""

    hass.data.setdefault(DOMAIN, {})

    username = entry.data[CONF_USERNAME]
    password = entry.data[CONF_PASSWORD]
    with_family = entry.data[CONF_WITH_FAMILY]
    max_interval = entry.data[CONF_MAX_INTERVAL]
    gps_accuracy_threshold = entry.data[CONF_GPS_ACCURACY_THRESHOLD]

    # For backwards compat
    if entry.unique_id is None:
        hass.config_entries.async_update_entry(entry, unique_id=username)

    icloud_dir = Store[Any](hass, STORAGE_VERSION, STORAGE_KEY)

    account = IcloudAccount(
        hass,
        username,
        password,
        icloud_dir,
        with_family,
        max_interval,
        gps_accuracy_threshold,
        entry,
    )
    await hass.async_add_executor_job(account.setup)

    hass.data[DOMAIN][entry.unique_id] = account

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    register_services(hass)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.data[CONF_USERNAME])
    return unload_ok
