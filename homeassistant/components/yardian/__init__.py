"""The Yardian integration."""
from __future__ import annotations

from pyyardian import AsyncYardianClient
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import DOMAIN, MAX_ZONES
from .coordinator import YardianUpdateCoordinator

PLATFORMS: list[Platform] = [Platform.SWITCH]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional("device", default=[]): vol.Schema(
                    [
                        {
                            vol.Required("yid"): cv.string,
                            vol.Required("host"): cv.string,
                            vol.Required("access_token"): cv.string,
                            vol.Optional("duration"): vol.Schema(
                                {
                                    vol.Optional(i + 1): cv.positive_int
                                    for i in range(MAX_ZONES)
                                },
                                extra=vol.ALLOW_EXTRA,
                            ),
                        }
                    ]
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

    device_config = next(
        filter(
            lambda d: d["yid"].lower() == entry.data["yid"].lower(),
            hass.data[DOMAIN]["config"]["device"],
        )
    )
    host = device_config["host"] if device_config else entry.data["host"]
    access_token = (
        device_config["access_token"] if device_config else entry.data["access_token"]
    )

    controller = AsyncYardianClient(async_get_clientsession(hass), host, access_token)
    coordinator = YardianUpdateCoordinator(hass, entry, controller, device_config)
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)

    return unload_ok
