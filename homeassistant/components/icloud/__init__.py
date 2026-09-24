"""The iCloud component."""

from typing import Any

from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.storage import Store
from homeassistant.helpers.typing import ConfigType

from .account import IcloudAccount, IcloudConfigEntry
from .const import (
    CONF_GPS_ACCURACY_THRESHOLD,
    CONF_MAX_INTERVAL,
    CONF_WITH_FAMILY,
    DOMAIN,
    PLATFORMS,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .coordinator import IcloudCalendarCoordinator
from .media_source import async_setup_mediasource, async_setup_photo_cache
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up iCloud integration."""

    async_setup_services(hass)
    async_setup_mediasource(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: IcloudConfigEntry) -> bool:
    """Set up an iCloud account from a config entry."""

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

    entry.runtime_data = account

    await hass.async_add_executor_job(account.setup)

    # Refreshed before the platforms are forwarded so the calendars are known
    # by the time the calendar platform sets up. This deliberately does not use
    # async_config_entry_first_refresh: an account that fails to authenticate
    # still loads and starts a reauth flow, and a calendar outage should not
    # take device tracking down with it. Calendars that are missing from the
    # first refresh appear on a later one through the coordinator listener.
    account.calendar_coordinator = IcloudCalendarCoordinator(hass, entry)
    await account.calendar_coordinator.async_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_setup_photo_cache(hass, account)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: IcloudConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        await hass.async_add_executor_job(entry.runtime_data.cancel_fetch)
    return unload_ok
