"""The GTFS integration."""

from functools import partial
import threading

from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady

from .const import CONF_DATABASE, DOMAIN
from .feed import (
    CannotConnect,
    GtfsConfigEntry,
    InvalidFeed,
    async_fetch_feed,
    close_feed,
    feed_database_path,
    open_feed,
)

PLATFORMS = [Platform.CALENDAR]


async def async_setup_entry(hass: HomeAssistant, entry: GtfsConfigEntry) -> None:
    """Set up a GTFS feed from a config entry."""
    db_path = feed_database_path(hass, entry.data[CONF_DATABASE])
    if not await hass.async_add_executor_job(db_path.exists):
        try:
            await async_fetch_feed(
                hass, entry.data[CONF_URL], db_path, threading.Event()
            )
        except CannotConnect as err:
            raise ConfigEntryNotReady(
                translation_domain=DOMAIN, translation_key="cannot_connect"
            ) from err
        except InvalidFeed as err:
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="invalid_feed",
                translation_placeholders={"error": str(err)},
            ) from err
    entry.runtime_data = await hass.async_add_executor_job(open_feed, db_path)
    # Route subentry changes only fire update listeners.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def _async_update_listener(hass: HomeAssistant, entry: GtfsConfigEntry) -> None:
    """Reload the entry when routes are added or removed."""
    hass.config_entries.async_schedule_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: GtfsConfigEntry) -> None:
    """Unload a config entry."""
    await hass.config_entries.async_unload_platforms_or_raise(entry, PLATFORMS)
    await hass.async_add_executor_job(close_feed, entry.runtime_data)


async def async_remove_entry(hass: HomeAssistant, entry: GtfsConfigEntry) -> None:
    """Delete the feed database."""
    db_path = feed_database_path(hass, entry.data[CONF_DATABASE])
    await hass.async_add_executor_job(partial(db_path.unlink, missing_ok=True))
