"""
Support for Somfy hubs.

For more details about this component, please refer to the documentation at
https://home-assistant.io/components/somfy/
"""
import logging
from datetime import timedelta
from functools import partial

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries
from homeassistant.components.somfy import config_flow
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_TOKEN
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import Throttle

API = "api"

DEVICES = "devices"

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=10)

DOMAIN = "somfy"

CONF_CLIENT_ID = "client_id"
CONF_CLIENT_SECRET = "client_secret"

SOMFY_AUTH_CALLBACK_PATH = "/auth/somfy/callback"
SOMFY_AUTH_START = "/auth/somfy"

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

SOMFY_COMPONENTS = ["cover"]


async def async_setup(hass, config):
    """Set up the Somfy component."""
    if DOMAIN not in config:
        return True

    hass.data[DOMAIN] = {}

    config_flow.register_flow_implementation(
        hass, config[DOMAIN][CONF_CLIENT_ID], config[DOMAIN][CONF_CLIENT_SECRET]
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up Somfy from a config entry."""

    def token_saver(token):
        _LOGGER.debug("Saving updated token")
        entry.data[CONF_TOKEN] = token
        update_entry = partial(
            hass.config_entries.async_update_entry, data={**entry.data}
        )
        hass.add_job(update_entry, entry)

    # Force token update.
    from pymfy.api.somfy_api import SomfyApi

    hass.data[DOMAIN][API] = SomfyApi(
        entry.data["refresh_args"]["client_id"],
        entry.data["refresh_args"]["client_secret"],
        token=entry.data[CONF_TOKEN],
        token_updater=token_saver,
    )

    await update_all_devices(hass)

    for component in SOMFY_COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data[DOMAIN].pop(API, None)
    return True


class SomfyEntity(Entity):
    """Representation of a generic Somfy device."""

    def __init__(self, device, api):
        """Initialize the Somfy device."""
        self.device = device
        self.api = api

    @property
    def unique_id(self):
        """Return the unique id base on the id returned by Somfy."""
        return self.device.id

    @property
    def name(self):
        """Return the name of the device."""
        return self.device.name

    @property
    def device_info(self):
        """Return device specific attributes.

        Implemented by platform classes.
        """
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": self.name,
            "model": self.device.type,
            "via_hub": (DOMAIN, self.device.site_id),
            # For the moment, Somfy only returns their own device.
            "manufacturer": "Somfy",
        }

    async def async_update(self):
        """Update the device with the latest data."""
        await update_all_devices(self.hass)
        devices = self.hass.data[DOMAIN][DEVICES]
        self.device = next((d for d in devices if d.id == self.device.id), self.device)

    def has_capability(self, capability):
        """Test if device has a capability."""
        capabilities = self.device.capabilities
        return bool([c for c in capabilities if c.name == capability])


@Throttle(SCAN_INTERVAL)
async def update_all_devices(hass):
    """Update all the devices."""
    from requests import HTTPError
    from oauthlib.oauth2 import TokenExpiredError

    try:
        data = hass.data[DOMAIN]
        data[DEVICES] = await hass.async_add_executor_job(data[API].get_devices)
    except TokenExpiredError:
        _LOGGER.warning("Cannot update devices due to expired token")
    except HTTPError:
        _LOGGER.warning("Cannot update devices")
