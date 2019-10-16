"""
Support for Somfy hubs.

For more details about this component, please refer to the documentation at
https://home-assistant.io/integrations/somfy/
"""
import asyncio
import logging
from datetime import timedelta

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant import config_entries, exceptions
from homeassistant.components.somfy import config_flow
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.util import Throttle

from . import local_auth
from .const import DATA_IMPLEMENTATION

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
    hass.data[DOMAIN] = {DATA_IMPLEMENTATION: {}}

    if DOMAIN not in config:
        return True

    config_flow.register_flow_implementation(
        hass,
        local_auth.LocalSomfyImplementation(
            hass, config[DOMAIN][CONF_CLIENT_ID], config[DOMAIN][CONF_CLIENT_SECRET]
        ),
    )

    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}
    )

    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Set up Somfy from a config entry."""
    implementation_domain = entry.data.get(
        "domain",
        # Fallback for backwards compat
        DOMAIN,
    )
    implementation = hass.data[DOMAIN][DATA_IMPLEMENTATION].get(implementation_domain)

    if not implementation:
        raise exceptions.HomeAssistantError(
            f"Unknown implementation: {implementation_domain}"
        )

    hass.data[DOMAIN][API] = implementation.async_create_api_auth(entry)

    await update_all_devices(hass)

    for component in SOMFY_COMPONENTS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True


async def async_unload_entry(hass: HomeAssistantType, entry: ConfigEntry):
    """Unload a config entry."""
    hass.data[DOMAIN].pop(API, None)
    await asyncio.gather(
        *[
            hass.config_entries.async_forward_entry_unload(entry, component)
            for component in SOMFY_COMPONENTS
        ]
    )
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
