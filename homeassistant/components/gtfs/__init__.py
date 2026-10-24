"""The GTFS integration."""

import datetime as dt
from functools import partial
import logging
from pathlib import Path
import threading

from homeassistant.const import CONF_URL, Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, issue_registry as ir
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import CONF_DATABASE, DOMAIN, FLOW_DATABASES
from .feed import (
    CannotConnect,
    GtfsConfigEntry,
    InvalidFeed,
    async_fetch_feed,
    close_feed,
    feed_database_path,
    list_files,
    open_feed,
    remove_files,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.platform_only_config_schema(DOMAIN)

PLATFORMS = [Platform.CALENDAR]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Remove feed files that no config entry or flow owns.

    Home Assistant can stop during an import, or between a reconfigure saving
    its new database and deleting the old one.
    """
    files = await hass.async_add_executor_job(
        list_files, Path(hass.config.cache_path(DOMAIN))
    )
    # Setup can run while another flow is importing, so its files are kept. A
    # listed file's owner named it before creating it, so it is known by now.
    flow_databases = hass.data.get(FLOW_DATABASES, set())
    databases = {
        entry.data[CONF_DATABASE] for entry in hass.config_entries.async_entries(DOMAIN)
    } | flow_databases
    kept = {Path(database).stem for database in databases}
    orphans = [path for path in files if path.name.partition(".")[0] not in kept]
    removed = await hass.async_add_executor_job(remove_files, orphans)
    _LOGGER.debug("Removed %d orphaned feed files", removed)
    return True


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
    last_date = entry.runtime_data.last_service_date
    _async_check_expired(hass, entry, last_date)

    @callback
    def _async_check_expired_daily(now: dt.datetime) -> None:
        _async_check_expired(hass, entry, last_date)

    entry.async_on_unload(
        async_track_time_change(
            hass, _async_check_expired_daily, hour=0, minute=0, second=0
        )
    )
    entry.async_on_unload(
        partial(ir.async_delete_issue, hass, DOMAIN, _expired_issue_id(entry))
    )
    # Route subentry changes only fire update listeners.
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


def _expired_issue_id(entry: GtfsConfigEntry) -> str:
    return f"feed_expired_{entry.entry_id}"


@callback
def _async_check_expired(
    hass: HomeAssistant, entry: GtfsConfigEntry, last_date: dt.date | None
) -> None:
    """Raise an issue once the feed has no service left."""
    if last_date is None or last_date >= dt_util.now().date():
        ir.async_delete_issue(hass, DOMAIN, _expired_issue_id(entry))
        return
    ir.async_create_issue(
        hass,
        DOMAIN,
        _expired_issue_id(entry),
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="feed_expired",
        translation_placeholders={
            "title": entry.title,
            "last_date": last_date.isoformat(),
        },
    )


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
