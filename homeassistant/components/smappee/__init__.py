"""The Smappee integration."""
import asyncio

from pysmappee import Smappee
import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_IP_ADDRESS,
    CONF_PLATFORM,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.util import Throttle

from . import api, config_flow
from .const import (
    AUTHORIZE_URL,
    CONF_SERIALNUMBER,
    DOMAIN,
    MIN_TIME_BETWEEN_UPDATES,
    PLATFORMS,
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
    """Set up the Smappee component."""
    hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    client_id = config[DOMAIN][CONF_CLIENT_ID]
    hass.data[DOMAIN][client_id] = {}

    # decide platform
    platform = "PRODUCTION"
    if client_id == "homeassistant_f2":
        platform = "ACCEPTANCE"
    elif client_id == "homeassistant_f3":
        platform = "DEVELOPMENT"

    hass.data[DOMAIN][CONF_PLATFORM] = platform

    config_flow.SmappeeFlowHandler.async_register_implementation(
        hass,
        config_entry_oauth2_flow.LocalOAuth2Implementation(
            hass,
            DOMAIN,
            config[DOMAIN][CONF_CLIENT_ID],
            config[DOMAIN][CONF_CLIENT_SECRET],
            AUTHORIZE_URL[platform],
            TOKEN_URL[platform],
        ),
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Smappee from a zeroconf or config entry."""
    if CONF_IP_ADDRESS in entry.data:
        smappee_api = api.api.SmappeeLocalApi(ip=entry.data[CONF_IP_ADDRESS])
        smappee = Smappee(api=smappee_api, serialnumber=entry.data[CONF_SERIALNUMBER])
        await hass.async_add_executor_job(smappee.load_local_service_location)
    else:
        implementation = (
            await config_entry_oauth2_flow.async_get_config_entry_implementation(
                hass, entry
            )
        )

        smappee_api = api.ConfigEntrySmappeeApi(hass, entry, implementation)

        smappee = Smappee(api=smappee_api)
        await hass.async_add_executor_job(smappee.load_service_locations)

    hass.data[DOMAIN][entry.entry_id] = SmappeeBase(hass, smappee)

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok


class SmappeeBase:
    """An object to hold the PySmappee instance."""

    def __init__(self, hass, smappee):
        """Initialize the Smappee API wrapper class."""
        self.hass = hass
        self.smappee = smappee

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Update all Smappee trends and appliance states."""
        await self.hass.async_add_executor_job(
            self.smappee.update_trends_and_appliance_states
        )
