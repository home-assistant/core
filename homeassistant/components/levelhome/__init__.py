"""The Level Lock integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from . import auth as auth_mod
from ._lib.level_ha import WebsocketManager as LevelWebsocketManager
from .const import (
    CONF_OAUTH2_BASE_URL,
    CONF_PARTNER_BASE_URL,
    DEFAULT_PARTNER_BASE_URL,
    DOMAIN,
)
from .coordinator import LevelLocksCoordinator

# For your initial PR, limit it to 1 platform.
_PLATFORMS: list[Platform] = [Platform.LOCK]

type LevelHomeConfigEntry = ConfigEntry[LevelLocksCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: LevelHomeConfigEntry) -> bool:
    """Set up Level Lock from a config entry."""
    _LOGGER = logging.getLogger(__name__)

    _LOGGER.info("Setting up Level Lock config entry")
    if entry.options:
        hass.data.setdefault(DOMAIN, {})[CONF_OAUTH2_BASE_URL] = entry.options.get(
            CONF_OAUTH2_BASE_URL
        )
        hass.data[DOMAIN][CONF_PARTNER_BASE_URL] = entry.options.get(
            CONF_PARTNER_BASE_URL
        )
    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    oauth_session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    client_session = aiohttp_client.async_get_clientsession(hass)
    config_auth = auth_mod.AsyncConfigEntryAuth(client_session, oauth_session)

    _LOGGER.info("Ensuring token is valid before starting WebSocket")
    await oauth_session.async_ensure_token_valid()
    _LOGGER.info("Token validated, proceeding with setup")

    base_url = (hass.data.get(DOMAIN) or {}).get(
        CONF_PARTNER_BASE_URL
    ) or DEFAULT_PARTNER_BASE_URL
    _LOGGER.info("Using base URL: %s", base_url)

    async def _get_token() -> str:
        return await config_auth.async_get_access_token()

    async def _on_state(
        lock_id: str, is_locked: bool | None, payload: dict | None
    ) -> None:
        await coordinator.async_handle_push_update(lock_id, is_locked, payload)

    async def _on_devices(devices: list[dict]) -> None:
        await coordinator.async_handle_devices_update(devices)

    ws_manager = LevelWebsocketManager(
        client_session, base_url, _get_token, _on_state, _on_devices
    )
    _LOGGER.info("Starting WebSocket manager")
    await ws_manager.async_start()
    _LOGGER.info("WebSocket manager started")

    coordinator = LevelLocksCoordinator(hass, ws_manager, config_entry=entry)
    _LOGGER.info("Starting coordinator first refresh")
    await coordinator.async_config_entry_first_refresh()
    _LOGGER.info(
        "Coordinator first refresh completed with %d devices: %s",
        len(coordinator.data) if coordinator.data else 0,
        list(coordinator.data.keys()) if coordinator.data else [],
    )

    entry.runtime_data = coordinator

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "ws_manager": ws_manager,
    }

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)
    _LOGGER.info("Level Lock setup completed")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: LevelHomeConfigEntry) -> bool:
    """Unload a config entry."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, _PLATFORMS)
    if DOMAIN in hass.data and entry.entry_id in hass.data[DOMAIN]:
        data = hass.data[DOMAIN].pop(entry.entry_id, {})
        ws_manager: LevelWebsocketManager | None = data.get("ws_manager")
        if ws_manager is not None:
            await ws_manager.async_stop()
    return unloaded
