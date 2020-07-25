"""Google integration."""
import asyncio
import logging
import os

import voluptuous as vol

from homeassistant.components import webhook
from homeassistant.components.webhook import (
    async_unregister as async_unregister_webhook,
)
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_WEBHOOK_ID
from homeassistant.core import Config, HomeAssistant
from homeassistant.helpers import (
    aiohttp_client,
    config_entry_oauth2_flow,
    config_validation as cv,
    device_registry as dr,
)

from . import api, config_flow
from .const import (
    CONF_CALENDAR,
    CONFIG,
    CONF_SCOPES,
    DOMAIN,
    PLATFORMS,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    SCOPES,
)

from . import legacy

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


def setup(hass: HomeAssistant, config: Config) -> bool:
    """Set up the legacy Google integration."""
    legacy.setup(hass, config)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google from a config entry."""
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN][entry.entry_id] = {}

    config_flow.GoogleOAuth2ConfigFlow.async_register_implementation(
        hass,
        config_flow.GoogleLocalOAuth2Implementation(
            hass,
            DOMAIN,
            entry.data.get(CONF_CLIENT_ID),
            entry.data.get(CONF_CLIENT_SECRET),
            OAUTH2_AUTHORIZE,
            OAUTH2_TOKEN,
        ),
    )

    try:
        implementation = await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    except ValueError:
        _LOGGER.warning(
            "Integration misconfigured.  Go to Configuration > Integrations > + > Google"
        )
        return False
    else:
        # If using a requests-based API lib
        google_api = api.ConfigEntryAuth(hass, entry, implementation)

        if not await hass.async_add_executor_job(google_api.setup):
            _LOGGER.error("Unable to setup Google API service")
            return False

        hass.data[DOMAIN][entry.entry_id] = google_api

        for component in PLATFORMS:
            hass.async_create_task(
                hass.config_entries.async_forward_entry_setup(entry, component)
            )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""

    await asyncio.gather(
        hass.config_entries.async_forward_entry_unload(entry, CONF_CALENDAR),
    )

    return True


# async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
#     """Remove a config entry."""
#     return True
