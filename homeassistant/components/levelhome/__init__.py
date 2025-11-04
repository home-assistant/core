"""The Level Lock integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client, config_entry_oauth2_flow

from . import auth as auth_mod
from ._lib.level_ha import (
    Client as LibClient,
    WebsocketManager as LevelWebsocketManager,
)
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
    # Store selected base URLs for runtime access by application_credentials
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

    # Use an aiohttp-based auth helper for async calls
    client_session = aiohttp_client.async_get_clientsession(hass)
    config_auth = auth_mod.AsyncConfigEntryAuth(client_session, oauth_session)

    # Build resource API client and coordinator here (bind config_entry to coordinator)
    # Use the partner base URL for device APIs
    base_url = (hass.data.get(DOMAIN) or {}).get(
        CONF_PARTNER_BASE_URL
    ) or DEFAULT_PARTNER_BASE_URL

    async def _get_token() -> str:
        return await config_auth.async_get_access_token()

    client = LibClient(client_session, base_url, _get_token)
    coordinator = LevelLocksCoordinator(hass, client, config_entry=entry)
    # First refresh: if it fails due to network/auth, raise ConfigEntryNotReady here
    await coordinator.async_config_entry_first_refresh()

    # Set up websocket push manager
    async def _on_state(
        lock_id: str, is_locked: bool | None, payload: dict | None
    ) -> None:
        await coordinator.async_handle_push_update(lock_id, is_locked, payload)

    ws_manager = LevelWebsocketManager(client_session, base_url, _get_token, _on_state)
    coordinator.attach_ws_manager(ws_manager)
    await coordinator.async_start_push()

    # Store coordinator in runtime_data
    entry.runtime_data = coordinator

    # Store ws_manager for cleanup during unload
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "ws_manager": ws_manager,
    }

    await hass.config_entries.async_forward_entry_setups(entry, _PLATFORMS)

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
