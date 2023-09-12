"""The Yardian integration."""
from __future__ import annotations

from pyyardian import AsyncYardianClient
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN
from .coordinator import YardianUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SWITCH]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional("duration", default={}): vol.All(
                    {
                        vol.Required(cv.string): cv.positive_int,
                    },
                    vol.Length(min=1),
                ),
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up for Yardian."""

    hass.data[DOMAIN] = {
        "config": config.get(DOMAIN, {}),
    }

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Yardian from a config entry."""

    host = entry.data[CONF_HOST]
    access_token = entry.data[CONF_ACCESS_TOKEN]

    controller = AsyncYardianClient(async_get_clientsession(hass), host, access_token)
    coordinator = YardianUpdateCoordinator(hass, entry, controller)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)

    return unload_ok
