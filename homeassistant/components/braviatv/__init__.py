"""The Bravia TV integration."""
from __future__ import annotations

from typing import Final

from aiohttp import CookieJar
from pybravia import BraviaTV

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PIN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_create_clientsession

from .const import CONF_IGNORED_SOURCES, CONF_USE_PSK, DOMAIN
from .coordinator import BraviaTVCoordinator

PLATFORMS: Final[list[Platform]] = [
    Platform.BUTTON,
    Platform.MEDIA_PLAYER,
    Platform.REMOTE,
]


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up a config entry."""
    host = config_entry.data[CONF_HOST]
    mac = config_entry.data[CONF_MAC]
    pin = config_entry.data[CONF_PIN]
    use_psk = config_entry.data.get(CONF_USE_PSK, False)
    ignored_sources = config_entry.options.get(CONF_IGNORED_SOURCES, [])

    session = async_create_clientsession(
        hass, cookie_jar=CookieJar(unsafe=True, quote_cookie=False)
    )
    client = BraviaTV(host, mac, session=session)
    coordinator = BraviaTVCoordinator(
        hass=hass,
        client=client,
        pin=pin,
        use_psk=use_psk,
        ignored_sources=ignored_sources,
    )
    config_entry.async_on_unload(config_entry.add_update_listener(update_listener))

    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(
        config_entry, PLATFORMS
    )

    if unload_ok:
        hass.data[DOMAIN].pop(config_entry.entry_id)

    return unload_ok


async def update_listener(hass: HomeAssistant, config_entry: ConfigEntry) -> None:
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
