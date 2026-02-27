"""The madVR Envy integration."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from madvr_envy import MadvrEnvyClient
from madvr_envy import exceptions as envy_exceptions

from .const import (
    DEFAULT_COMMAND_TIMEOUT,
    DEFAULT_CONNECT_TIMEOUT,
    DEFAULT_READ_TIMEOUT,
    DEFAULT_RECONNECT_INITIAL_BACKOFF,
    DEFAULT_RECONNECT_JITTER,
    DEFAULT_RECONNECT_MAX_BACKOFF,
    DEFAULT_SYNC_TIMEOUT,
    DOMAIN,
    OPT_COMMAND_TIMEOUT,
    OPT_CONNECT_TIMEOUT,
    OPT_READ_TIMEOUT,
    OPT_RECONNECT_INITIAL_BACKOFF,
    OPT_RECONNECT_JITTER,
    OPT_RECONNECT_MAX_BACKOFF,
    OPT_SYNC_TIMEOUT,
    PLATFORMS,
)
from .coordinator import MadvrEnvyCoordinator
from .models import MadvrEnvyRuntimeData
from .services import async_setup_services, async_unload_services

MadvrEnvyConfigEntry = ConfigEntry


async def async_setup_entry(hass: HomeAssistant, entry: MadvrEnvyConfigEntry) -> bool:
    """Set up madVR Envy from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]

    client = MadvrEnvyClient(
        host=host,
        port=port,
        connect_timeout=_get_float_option(entry, OPT_CONNECT_TIMEOUT, DEFAULT_CONNECT_TIMEOUT),
        command_timeout=_get_float_option(entry, OPT_COMMAND_TIMEOUT, DEFAULT_COMMAND_TIMEOUT),
        read_timeout=_get_float_option(entry, OPT_READ_TIMEOUT, DEFAULT_READ_TIMEOUT),
        reconnect_initial_backoff=_get_float_option(
            entry,
            OPT_RECONNECT_INITIAL_BACKOFF,
            DEFAULT_RECONNECT_INITIAL_BACKOFF,
        ),
        reconnect_max_backoff=_get_float_option(
            entry,
            OPT_RECONNECT_MAX_BACKOFF,
            DEFAULT_RECONNECT_MAX_BACKOFF,
        ),
        reconnect_jitter=_get_float_option(
            entry,
            OPT_RECONNECT_JITTER,
            DEFAULT_RECONNECT_JITTER,
        ),
        auto_reconnect=True,
    )
    coordinator = MadvrEnvyCoordinator(
        hass,
        client,
        sync_timeout=_get_float_option(entry, OPT_SYNC_TIMEOUT, DEFAULT_SYNC_TIMEOUT),
    )

    try:
        await coordinator.async_start()
    except (
        envy_exceptions.ConnectionFailedError,
        envy_exceptions.ConnectionTimeoutError,
        TimeoutError,
    ) as err:
        await coordinator.async_shutdown()
        raise ConfigEntryNotReady(f"Could not connect to madVR Envy at {host}:{port}") from err
    except Exception:
        await coordinator.async_shutdown()
        raise

    runtime_data = MadvrEnvyRuntimeData(client=client, coordinator=coordinator, last_data={})
    entry.runtime_data = runtime_data
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = runtime_data
    await async_setup_services(hass)

    async def _handle_hass_stop(_event: Event) -> None:
        await coordinator.async_shutdown()

    entry.async_on_unload(hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, _handle_hass_stop))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: MadvrEnvyConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        await entry.runtime_data.coordinator.async_shutdown()
        if not hass.data[DOMAIN]:
            await async_unload_services(hass)
            hass.data.pop(DOMAIN, None)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: MadvrEnvyConfigEntry) -> None:
    """Handle reload request."""
    await hass.config_entries.async_reload(entry.entry_id)


def _get_float_option(entry: ConfigEntry, key: str, default: float) -> float:
    value: Any = entry.options.get(key, default)
    return float(value)
