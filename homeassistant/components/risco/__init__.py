"""The Risco integration."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import logging
from typing import Any

from pyrisco import CannotConnectError, RiscoCloud, RiscoLocal, UnauthorizedError
from pyrisco.common import Partition, System, Zone

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
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import (
    CONF_CONCURRENCY,
    DATA_COORDINATOR,
    DEFAULT_CONCURRENCY,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    EVENTS_COORDINATOR,
    SYSTEM_UPDATE_SIGNAL,
    TYPE_LOCAL,
)
from .coordinator import RiscoDataUpdateCoordinator, RiscoEventsDataUpdateCoordinator

PLATFORMS = [
    Platform.ALARM_CONTROL_PANEL,
    Platform.BINARY_SENSOR,
    Platform.SENSOR,
    Platform.SWITCH,
]
_LOGGER = logging.getLogger(__name__)


@dataclass
class LocalData:
    """A data class for local data passed to the platforms."""

    system: RiscoLocal
    partition_updates: dict[int, Callable[[], Any]] = field(default_factory=dict)


def is_local(entry: ConfigEntry) -> bool:
    """Return whether the entry represents an instance with local communication."""
    return entry.data.get(CONF_TYPE) == TYPE_LOCAL


def zone_update_signal(zone_id: int) -> str:
    """Return a signal for the dispatch of a zone update."""
    return f"risco_zone_update_{zone_id}"


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Risco from a config entry."""
    if is_local(entry):
        return await _async_setup_local_entry(hass, entry)

    return await _async_setup_cloud_entry(hass, entry)


async def _async_setup_local_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = entry.data
    concurrency = entry.options.get(CONF_CONCURRENCY, DEFAULT_CONCURRENCY)
    risco = RiscoLocal(
        data[CONF_HOST], data[CONF_PORT], data[CONF_PIN], concurrency=concurrency
    )

    try:
        await risco.connect()
    except CannotConnectError as error:
        raise ConfigEntryNotReady from error
    except UnauthorizedError:
        _LOGGER.exception("Failed to login to Risco cloud")
        return False

    async def _error(error: Exception) -> None:
        _LOGGER.error("Error in Risco library", exc_info=error)

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

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = local_data
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_setup_cloud_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = entry.data
    risco = RiscoCloud(data[CONF_USERNAME], data[CONF_PASSWORD], data[CONF_PIN])
    try:
        await risco.login(async_get_clientsession(hass))
    except CannotConnectError as error:
        raise ConfigEntryNotReady from error
    except UnauthorizedError as error:
        raise ConfigEntryAuthFailed from error

    scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = RiscoDataUpdateCoordinator(hass, risco, scan_interval)
    await coordinator.async_config_entry_first_refresh()
    events_coordinator = RiscoEventsDataUpdateCoordinator(
        hass, risco, entry.entry_id, 60
    )

    entry.async_on_unload(entry.add_update_listener(_update_listener))

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
        EVENTS_COORDINATOR: events_coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await events_coordinator.async_refresh()

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        if is_local(entry):
            local_data: LocalData = hass.data[DOMAIN][entry.entry_id]
            await local_data.system.disconnect()

        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(entry.entry_id)
