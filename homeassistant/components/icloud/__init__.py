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
from .coordinator import IcloudCalendarCoordinator, IcloudRemindersCoordinator
from .media_source import async_setup_mediasource, async_setup_photo_cache
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up iCloud integration."""

    async_setup_services(hass)
    async_setup_mediasource(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: IcloudConfigEntry) -> None:
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

    account.calendar_coordinator = IcloudCalendarCoordinator(hass, entry)
    account.reminders_coordinator = IcloudRemindersCoordinator(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_setup_photo_cache(hass, account)

    # The first calendars and reminders fetch can take minutes on a large
    # account, which used to stall startup here, so it runs as a background
    # task instead. The platforms registered their coordinator listeners
    # during setup above, so whatever the first fetch brings back appears as it
    # lands and lists that show up on later polls are added then. This
    # deliberately does not use async_config_entry_first_refresh: an account
    # that fails to authenticate still loads and starts a reauth flow, and a
    # calendar or Reminders outage should not take device tracking down with it.
    entry.async_create_background_task(
        hass, _async_first_refresh(account), "icloud calendars and reminders refresh"
    )


async def _async_first_refresh(account: IcloudAccount) -> None:
    """Run the first calendars and reminders refresh off the setup path."""
    assert account.calendar_coordinator is not None
    assert account.reminders_coordinator is not None
    await account.calendar_coordinator.async_refresh()
    await account.reminders_coordinator.async_refresh()


async def async_unload_entry(hass: HomeAssistant, entry: IcloudConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    await hass.async_add_executor_job(entry.runtime_data.cancel_fetch)
