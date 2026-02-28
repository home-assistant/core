"""Integration for MyNeomitis."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

import aiohttp
import pyaxencoapi

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_EMAIL,
    CONF_PASSWORD,
    EVENT_HOMEASSISTANT_STOP,
    Platform,
)
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SELECT]


@dataclass
class MyNeomitisRuntimeData:
    """Runtime data for MyNeomitis integration."""

    api: pyaxencoapi.PyAxencoAPI
    devices: list[dict[str, Any]]


type MyNeomitisConfigEntry = ConfigEntry[MyNeomitisRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: MyNeomitisConfigEntry) -> bool:
    """Set up MyNeomitis from a config entry."""
    session = async_get_clientsession(hass)

    email: str = entry.data[CONF_EMAIL]
    password: str = entry.data[CONF_PASSWORD]

    api = pyaxencoapi.PyAxencoAPI(session)
    connected = False
    try:
        await api.login(email, password)
        await api.connect_websocket()
        connected = True
        _LOGGER.debug("Successfully connected to Login/WebSocket")

        # Retrieve the user's devices
        devices: list[dict[str, Any]] = await api.get_devices()

    except aiohttp.ClientResponseError as err:
        if connected:
            try:
                await api.disconnect_websocket()
            except (
                TimeoutError,
                ConnectionError,
                aiohttp.ClientError,
            ) as disconnect_err:
                _LOGGER.error(
                    "Error while disconnecting WebSocket for %s: %s",
                    entry.entry_id,
                    disconnect_err,
                )
        if err.status == 401:
            raise ConfigEntryAuthFailed(
                "Authentication failed, please update your credentials"
            ) from err
        raise ConfigEntryNotReady(f"Error connecting to API: {err}") from err
    except (TimeoutError, ConnectionError, aiohttp.ClientError) as err:
        if connected:
            try:
                await api.disconnect_websocket()
            except (
                TimeoutError,
                ConnectionError,
                aiohttp.ClientError,
            ) as disconnect_err:
                _LOGGER.error(
                    "Error while disconnecting WebSocket for %s: %s",
                    entry.entry_id,
                    disconnect_err,
                )
        raise ConfigEntryNotReady(f"Error connecting to API/WebSocket: {err}") from err

    entry.runtime_data = MyNeomitisRuntimeData(api=api, devices=devices)

    async def _async_disconnect_websocket(_event: Event) -> None:
        """Disconnect WebSocket on Home Assistant shutdown."""
        try:
            await api.disconnect_websocket()
        except (TimeoutError, ConnectionError, aiohttp.ClientError) as err:
            _LOGGER.error(
                "Error while disconnecting WebSocket for %s: %s",
                entry.entry_id,
                err,
            )

    entry.async_on_unload(
        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STOP, _async_disconnect_websocket
        )
    )

    # Load platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: MyNeomitisConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        try:
            await entry.runtime_data.api.disconnect_websocket()
        except (TimeoutError, ConnectionError) as err:
            _LOGGER.error(
                "Error while disconnecting WebSocket for %s: %s",
                entry.entry_id,
                err,
            )

    return unload_ok
