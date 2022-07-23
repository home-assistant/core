"""The Risco integration."""
from datetime import timedelta
import logging


from pyrisco import (
    CannotConnectError,
    OperationError,
    UnauthorizedError,
    RiscoCloud,
    RiscoLocal,
)

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_PORT,
    CONF_SCAN_INTERVAL,
    CONF_TYPE,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    DATA_COORDINATOR,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENTS_COORDINATOR,
    TYPE_LOCAL,
)

PLATFORMS = [Platform.ALARM_CONTROL_PANEL, Platform.BINARY_SENSOR, Platform.SENSOR]
UNDO_LISTENERS = "undo_listeners"
LAST_EVENT_STORAGE_VERSION = 1
LAST_EVENT_TIMESTAMP_KEY = "last_event_timestamp"
_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Risco from a config entry."""
    if entry.data.get(CONF_TYPE) != TYPE_LOCAL:
        return await _async_setup_cloud_entry(hass, entry)
    return await _async_setup_local_entry(hass, entry)


async def _async_setup_local_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = entry.data
    risco = RiscoLocal(data[CONF_HOST], data[CONF_PORT], data[CONF_PIN])

    try:
        await risco.connect()
    except CannotConnectError as error:
        raise ConfigEntryNotReady() from error
    except UnauthorizedError:
        _LOGGER.exception("Failed to login to Risco cloud")
        return False

    # async def _error(error):
    #     _LOGGER.error(f"Error in Risco library: {error}")

    # remove_error = risco.add_error_handler(_error)

    # async def _default(command, result, *params):
    #     _LOGGER.debug(
    #         f"Unhandled update from Risco library: {command}, {result}, {params}"
    #     )

    # remove_default = risco.add_default_handler(_default)

    # zone_updates = {}

    # async def _zone(zone_id, zone):
    #     _LOGGER.debug(f"Risco zone update for {zone_id}")
    #     cb = zone_updates.get(zone_id)
    #     if cb:
    #         cb()

    # remove_zone = risco.add_zone_handler(_zone)

    # partition_updates = {}

    # async def _partition(partition_id, partition):
    #     _LOGGER.debug(f"Risco partition update for {partition_id}")
    #     cb = partition_updates.get(partition_id)
    #     if cb:
    #         cb()

    # remove_partition = risco.add_partition_handler(_partition)

    # listenrs = [remove_error, remove_default, remove_zone, remove_partition]

    listenrs = []
    listenrs.append(entry.add_update_listener(_update_listener))

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        UNDO_LISTENERS: listenrs,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_setup_cloud_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = entry.data
    risco = RiscoCloud(data[CONF_USERNAME], data[CONF_PASSWORD], data[CONF_PIN])
    try:
        await risco.login(async_get_clientsession(hass))
    except CannotConnectError as error:
        raise ConfigEntryNotReady() from error
    except UnauthorizedError:
        _LOGGER.exception("Failed to login to Risco cloud")
        return False

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = RiscoDataUpdateCoordinator(hass, risco, scan_interval)
    await coordinator.async_config_entry_first_refresh()
    events_coordinator = RiscoEventsDataUpdateCoordinator(
        hass, risco, entry.entry_id, 60
    )

    undo_listener = entry.add_update_listener(_update_listener)

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        UNDO_LISTENERS: [undo_listener],
        EVENTS_COORDINATOR: events_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await events_coordinator.async_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        for undo in hass.data[DOMAIN][entry.entry_id][UNDO_LISTENERS]:
            undo()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


class RiscoDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching risco data."""

    def __init__(self, hass, risco, scan_interval):
        """Initialize global risco data updater."""
        self.risco = risco
        interval = timedelta(seconds=scan_interval)
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=interval,
        )

    async def _async_update_data(self):
        """Fetch data from risco."""
        try:
            return await self.risco.get_state()
        except (CannotConnectError, UnauthorizedError, OperationError) as error:
            raise UpdateFailed(error) from error


class RiscoEventsDataUpdateCoordinator(DataUpdateCoordinator):
    """Class to manage fetching risco data."""

    def __init__(self, hass, risco, eid, scan_interval):
        """Initialize global risco data updater."""
        self.risco = risco
        self._store = Store(
            hass, LAST_EVENT_STORAGE_VERSION, f"risco_{eid}_last_event_timestamp"
        )
        interval = timedelta(seconds=scan_interval)
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_events",
            update_interval=interval,
        )

    async def _async_update_data(self):
        """Fetch data from risco."""
        last_store = await self._store.async_load() or {}
        last_timestamp = last_store.get(
            LAST_EVENT_TIMESTAMP_KEY, "2020-01-01T00:00:00Z"
        )
        try:
            events = await self.risco.get_events(last_timestamp, 10)
        except (CannotConnectError, UnauthorizedError, OperationError) as error:
            raise UpdateFailed(error) from error

        if len(events) > 0:
            await self._store.async_save({LAST_EVENT_TIMESTAMP_KEY: events[0].time})

        return events
