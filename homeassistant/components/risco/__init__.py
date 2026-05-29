"""The Risco integration."""

from asyncio import CancelledError
import logging

from pyrisco import (
    CannotConnectError,
    MaxRetriesError,
    OperationError,
    RiscoCloud,
    RiscoLocal,
    UnauthorizedError,
)
from pyrisco.cloud.alarm import Alarm
from pyrisco.cloud.event import Event
from pyrisco.common import Partition, System, Zone

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PIN,
    CONF_PORT,
    CONF_TYPE,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_COMMUNICATION_DELAY,
    CONF_CONCURRENCY,
    DEFAULT_CONCURRENCY,
    DOMAIN,
    SYSTEM_UPDATE_SIGNAL,
    TYPE_LOCAL,
)
from .models import CloudData, LocalData, RiscoConfigEntry, RiscoData
from .services import async_setup_services

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
]
_LOGGER = logging.getLogger(__name__)
# pyrisco exposes timeout context as message text for this case.
CLOCK_TIMEOUT_ERROR_FRAGMENT = "Timeout in command: CLOCK"


def is_local(entry: ConfigEntry) -> bool:
    """Return whether the entry represents an instance with local communication."""
    return entry.data.get(CONF_TYPE) == TYPE_LOCAL


def zone_update_signal(zone_id: int) -> str:
    """Return a signal for the dispatch of a zone update."""
    return f"risco_zone_update_{zone_id}"


def cloud_update_signal(entry_id: str) -> str:
    """Return a signal for the dispatch of a cloud state update."""
    return f"risco_cloud_update_{entry_id}"


def cloud_event_signal(entry_id: str) -> str:
    """Return a signal for the dispatch of a cloud event update."""
    return f"risco_cloud_event_{entry_id}"


async def async_setup_entry(hass: HomeAssistant, entry: RiscoConfigEntry) -> bool:
    """Set up Risco from a config entry."""
    if is_local(entry):
        return await _async_setup_local_entry(hass, entry)

    return await _async_setup_cloud_entry(hass, entry)


async def _async_setup_local_entry(
    hass: HomeAssistant, entry: RiscoConfigEntry
) -> bool:
    data = entry.data
    concurrency = entry.options.get(CONF_CONCURRENCY, DEFAULT_CONCURRENCY)
    risco = RiscoLocal(
        data[CONF_HOST],
        data[CONF_PORT],
        data[CONF_PIN],
        communication_delay=data.get(CONF_COMMUNICATION_DELAY, 0),
        concurrency=concurrency,
    )

    try:
        await risco.connect()
    except CannotConnectError as error:
        raise ConfigEntryNotReady from error
    except UnauthorizedError:
        _LOGGER.exception("Failed to authenticate with local Risco panel")
        return False

    async def _error(error: Exception) -> None:
        if isinstance(error, OperationError) and CLOCK_TIMEOUT_ERROR_FRAGMENT in str(
            error
        ):
            _LOGGER.warning(
                "Risco keep-alive timeout for entry %s (host: %s)",
                entry.title,
                data.get(CONF_HOST, "unknown"),
            )
        else:
            _LOGGER.error(
                "Error in Risco library",
                exc_info=error,
            )
            if isinstance(error, ConnectionResetError) and not hass.is_stopping:
                _LOGGER.debug("Disconnected from panel. Reloading integration")
                hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))

    entry.async_on_unload(risco.add_error_handler(_error))

    async def _default(command: str, result: str, *params: list[str]) -> None:
        _LOGGER.debug(
            "Unhandled update from Risco library: %s, %s, %s", command, result, params
        )

    entry.async_on_unload(risco.add_default_handler(_default))

    local_data = LocalData(risco)

    async def _zone(zone_id: int, zone: Zone) -> None:
        _LOGGER.debug("Risco zone update for %d", zone_id)
        async_dispatcher_send(hass, zone_update_signal(zone_id))

    entry.async_on_unload(risco.add_zone_handler(_zone))

    async def _partition(partition_id: int, partition: Partition) -> None:
        _LOGGER.debug("Risco partition update for %d", partition_id)
        callback = local_data.partition_updates.get(partition_id)
        if callback:
            callback()

    entry.async_on_unload(risco.add_partition_handler(_partition))

    async def _system(system: System) -> None:
        _LOGGER.debug("Risco system update")
        async_dispatcher_send(hass, SYSTEM_UPDATE_SIGNAL)

    entry.async_on_unload(risco.add_system_handler(_system))

    entry.async_on_unload(entry.add_update_listener(_update_listener))

    entry.runtime_data = RiscoData(local_data=local_data)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_setup_cloud_entry(
    hass: HomeAssistant, entry: RiscoConfigEntry
) -> bool:
    data = entry.data
    risco = RiscoCloud(data[CONF_USERNAME], data[CONF_PASSWORD], data[CONF_PIN])
    try:
        await risco.login(async_get_clientsession(hass))
    except CannotConnectError as error:
        raise ConfigEntryNotReady from error
    except UnauthorizedError as error:
        raise ConfigEntryAuthFailed from error

    try:
        alarm = await risco.get_state()
    except (CannotConnectError, UnauthorizedError, OperationError) as error:
        await risco.close()
        raise ConfigEntryNotReady from error

    cloud_data = CloudData(system=risco, alarm=alarm)

    async def _state(new_alarm: Alarm) -> None:
        cloud_data.alarm = new_alarm
        async_dispatcher_send(hass, cloud_update_signal(entry.entry_id))

    async def _events(new_events: list[Event]) -> None:
        cloud_data.events = new_events
        async_dispatcher_send(hass, cloud_event_signal(entry.entry_id))

    async def _error(error: Exception) -> None:
        if isinstance(error, MaxRetriesError):
            _LOGGER.error(
                "Risco cloud SSE exhausted retries, reloading integration",
                exc_info=error,
            )
            if not hass.is_stopping:
                hass.async_create_task(hass.config_entries.async_reload(entry.entry_id))
        else:
            _LOGGER.warning(
                "Risco cloud SSE error (reconnecting automatically)", exc_info=error
            )

    remove_state_handler = risco.add_state_handler(_state)
    remove_event_handler = risco.add_event_handler(_events)
    remove_error_handler = risco.add_error_handler(_error)
    try:
        await risco.subscribe_states()
    except (CannotConnectError, UnauthorizedError, OperationError) as error:
        await risco.close()
        raise ConfigEntryNotReady from error

    entry.async_on_unload(risco.close)
    entry.async_on_unload(remove_state_handler)
    entry.async_on_unload(remove_event_handler)
    entry.async_on_unload(remove_error_handler)

    entry.async_on_unload(entry.add_update_listener(_update_listener))

    entry.runtime_data = RiscoData(cloud_data=cloud_data)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: RiscoConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok and (local_data := entry.runtime_data.local_data):
        try:
            await local_data.system.disconnect()
        except CancelledError:
            raise
        except Exception:
            _LOGGER.exception(
                "Failed to disconnect from local Risco panel for entry %s (host: %s)",
                entry.title,
                entry.data.get(CONF_HOST, "unknown"),
            )

    return unload_ok


async def _update_listener(hass: HomeAssistant, entry: RiscoConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Risco integration services."""

    await async_setup_services(hass)

    return True
