"""The Control4 integration."""
import asyncio
import voluptuous as vol
import datetime
import logging
import re

from pyControl4.account import C4Account
from pyControl4.director import C4Director

from homeassistant.helpers import entity
from homeassistant.helpers import device_registry as dr
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)

# TODO List the platforms that you want to support.
# For your initial PR, limit it to 1 platform.
PLATFORMS = ["light"]


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Control4 component."""

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Control4 from a config entry."""

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN].setdefault(entry.title, {})

    config = entry.data
    account = C4Account(config["username"], config["password"])
    await account.getAccountBearerToken()
    hass.data[DOMAIN][entry.title]["account"] = account

    director_token_dict = await account.getDirectorBearerToken(entry.title)
    director = C4Director(config["host"], director_token_dict["token"])
    hass.data[DOMAIN][entry.title]["director"] = director
    hass.data[DOMAIN][entry.title]["director_token_expiry"] = director_token_dict[
        "token_expiration"
    ]

    controller_href = (await account.getAccountControllers())["href"]
    hass.data[DOMAIN][entry.title][
        "director_sw_version"
    ] = await account.getControllerOSVersion(controller_href)

    result = re.search("_(.*)_", entry.title)
    hass.data[DOMAIN][entry.title]["director_model"] = result.group(1).upper()

    device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.title)},
        manufacturer="Control4",
        name=entry.title,
        model=hass.data[DOMAIN][entry.title]["director_model"],
        sw_version=hass.data[DOMAIN][entry.title]["director_sw_version"],
    )

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
        controller_name = entry.title
        hass.data[DOMAIN].pop(entry.title)
        _LOGGER.debug("Unloaded entry for %s", controller_name)

    return unload_ok


class Control4Controller(entity.Entity):
    def __init__(self, entry: ConfigEntry):
        self.entry = entry
        self.account = self.hass.data[DOMAIN][self.entry.title]["account"]
        self.director = self.hass.data[DOMAIN][self.entry.title]["director"]
        self.director_token_expiry = self.hass.data[DOMAIN][self.entry.title][
            "director_token_expiry"
        ]

    async def async_update(self):
        """Update the state of the device."""
        if (
            self.director_token_expiry is not None
            and datetime.datetime.now() < self.director_token_expiry
        ):
            _LOGGER.debug("Old director token is still valid. Not getting a new one.")
        else:
            config = self.entry.data
            self.account = C4Account(config["username"], config["password"])
            director_token_dict = await self.account.getDirectorBearerToken(
                self.entry.title
            )
            self.director = C4Director(config["host"], director_token_dict["token"])
            self.director_token_expiry = director_token_dict["token_expiration"]

            _LOGGER.debug("Saving new tokens in config_entry")
            self.hass.data[DOMAIN][self.entry.title]["account"] = self.account
            self.hass.data[DOMAIN][self.entry.title]["director"] = self.director
            self.hass.data[DOMAIN][self.entry.title][
                "director_token_expiry"
            ] = self.director_token_expiry

