"""The Control4 integration."""
import asyncio

import voluptuous as vol

import datetime

from pyControl4.account import C4Account
from pyControl4.director import C4Director

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = ["light"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Control4 component."""

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Control4 from a config entry."""
    # TODO Store an API object for your platforms to access
    config = entry.data
    account = C4Account(config["username"], config["password"])
    hass.data[DOMAIN][entry.title]["account"] = account

    director_token_dict = account.getDirectorBearerToken(entry.title)
    hass.data[DOMAIN][entry.title]["director"] = C4Director(
        config["host"], director_token_dict["token"]
    )
    hass.data[DOMAIN][entry.title]["director_token_expiry"] = director_token_dict[
        "token_expiration"
    ]

    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in PLATFORMS
            ]
        )
    )
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
