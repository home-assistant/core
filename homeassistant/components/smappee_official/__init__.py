"""The Smappee Official integration."""
import asyncio

from pysmappee import Smappee
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.util import Throttle

from . import api, config_flow
from .const import (
    API,
    AUTHORIZE_URL,
    BASE,
    DOMAIN,
    MIN_TIME_BETWEEN_UPDATES,
    SMAPPEE_PLATFORMS,
    TOKEN_URL,
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_ID): cv.string,
                vol.Required(CONF_CLIENT_SECRET): cv.string,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Smappee Official component."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    config_flow.SmappeeFlowHandler.async_register_implementation(
        hass,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
            AUTHORIZE_URL,
            TOKEN_URL,
        ),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Smappee Official from a config entry."""
    implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
        hass, entry
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)

    # If using a requests-based API lib
    hass.data[DOMAIN][API] = api.ConfigEntrySmappeeApi(hass, entry, session)

    smappee = await hass.async_add_executor_job(Smappee, hass.data[DOMAIN][API])
    await hass.async_add_executor_job(smappee.load_service_locations)

    hass.data[DOMAIN][BASE] = SmappeeBase(smappee=smappee, hass=hass)

    for component in SMAPPEE_PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data[DOMAIN].pop(API, None)
    hass.data[DOMAIN].pop(BASE, None)
    await asyncio.gather(
        *[
            hass.config_entries.async_forward_entry_unload(entry, component)
            for component in SMAPPEE_PLATFORMS
        ]
    )
    return True


class SmappeeBase:
    """An object to hold the PySmappee instance."""

    def __init__(self, smappee, hass):
        """Initialize the Smappee API wrapper class."""
        self.smappee = smappee
        self.hass = hass

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Update all Smappee trends and appliance states."""
        await self.hass.async_add_executor_job(
            self._smappee.update_trends_and_appliance_states
        )
