"""The Traccar Server integration."""

from __future__ import annotations

from datetime import timedelta

from aiohttp import CookieJar
from pytraccar import ApiClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_API_TOKEN,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_create_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .const import CONF_EVENTS, DOMAIN
from .coordinator import TraccarServerCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.SENSOR,
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Traccar Server from a config entry."""
    if CONF_API_TOKEN not in entry.data:
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="migrate_to_api_token",
        )
    client_session = async_create_clientsession(
        hass,
        cookie_jar=CookieJar(
            unsafe=not entry.data[CONF_SSL] or not entry.data[CONF_VERIFY_SSL]
        ),
    )
    coordinator = TraccarServerCoordinator(
        hass=hass,
        config_entry=entry,
        client=ApiClient(
            client_session=client_session,
            host=entry.data[CONF_HOST],
            port=entry.data[CONF_PORT],
            token=entry.data[CONF_API_TOKEN],
            ssl=entry.data[CONF_SSL],
            verify_ssl=entry.data[CONF_VERIFY_SSL],
        ),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    if entry.options.get(CONF_EVENTS):
        entry.async_on_unload(
            async_track_time_interval(
                hass,
                coordinator.import_events,
                timedelta(seconds=30),
                cancel_on_shutdown=True,
                name="traccar_server_import_events",
            )
        )

    entry.async_create_background_task(
        hass=hass,
        target=coordinator.subscribe(),
        name="Traccar Server subscription",
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle an options update."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate old entry."""

    if entry.version < 2:
        # Version 2: Remove username and password, only keep API token
        data = dict(entry.data)
        data.pop(CONF_USERNAME, None)
        data.pop(CONF_PASSWORD, None)
        hass.config_entries.async_update_entry(entry, data=data, version=2)
    return True
