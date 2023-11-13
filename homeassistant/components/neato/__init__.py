"""Support for Neato botvac connected vacuum cleaners."""
import logging

import aiohttp
from pybotvac import Account
from pybotvac.exceptions import NeatoException
import voluptuous as vol

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_TOKEN, Platform
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_entry_oauth2_flow, config_validation as cv
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType

from . import api
from .const import NEATO_CONFIG, NEATO_DOMAIN, NEATO_LOGIN
from .hub import NeatoHub

_LOGGER = logging.getLogger(__name__)


CONFIG_SCHEMA = vol.Schema(
    vol.All(
        cv.deprecated(NEATO_DOMAIN),
        {
            NEATO_DOMAIN: vol.Schema(
                {
                    vol.Required(CONF_CLIENT_ID): cv.string,
                    vol.Required(CONF_CLIENT_SECRET): cv.string,
                }
            )
        },
    ),
    extra=vol.ALLOW_EXTRA,
)

PLATFORMS = [
    Platform.CAMERA,
    Platform.VACUUM,
    Platform.SWITCH,
    Platform.SENSOR,
    Platform.BUTTON,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Neato component."""
    hass.data[NEATO_DOMAIN] = {}

    if NEATO_DOMAIN not in config:
        return True

    hass.data[NEATO_CONFIG] = config[NEATO_DOMAIN]
    await async_import_client_credential(
        hass,
        NEATO_DOMAIN,
        ClientCredential(
            config[NEATO_DOMAIN][CONF_CLIENT_ID],
            config[NEATO_DOMAIN][CONF_CLIENT_SECRET],
        ),
    )
    _LOGGER.warning(
        "Configuration of Neato integration in YAML is deprecated and "
        "will be removed in a future release; Your existing OAuth "
        "Application Credentials have been imported into the UI "
        "automatically and can be safely removed from your "
        "configuration.yaml file"
    )
    async_create_issue(
        hass,
        HOMEASSISTANT_DOMAIN,
        f"deprecated_yaml_{NEATO_DOMAIN}",
        breaks_in_ha_version="2024.2.0",
        is_fixable=False,
        issue_domain=NEATO_DOMAIN,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
        translation_placeholders={
            "domain": NEATO_DOMAIN,
            "integration_title": "Neato Botvac",
        },
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""
    if CONF_TOKEN not in entry.data:
        raise ConfigEntryAuthFailed

    implementation = (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
    )

    session = config_entry_oauth2_flow.OAuth2Session(hass, entry, implementation)
    try:
        await session.async_ensure_token_valid()
    except aiohttp.ClientResponseError as ex:
        _LOGGER.debug("API error: %s (%s)", ex.code, ex.message)
        if ex.code in (401, 403):
            raise ConfigEntryAuthFailed("Token not valid, trigger renewal") from ex
        raise ConfigEntryNotReady from ex

    neato_session = api.ConfigEntryAuth(hass, entry, implementation)
    hass.data[NEATO_DOMAIN][entry.entry_id] = neato_session
    hub = NeatoHub(hass, Account(neato_session))

    await hub.async_update_entry_unique_id(entry)

    try:
        await hass.async_add_executor_job(hub.update_robots)
    except NeatoException as ex:
        _LOGGER.debug("Failed to connect to Neato API")
        raise ConfigEntryNotReady from ex

    hass.data[NEATO_LOGIN] = hub

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[NEATO_DOMAIN].pop(entry.entry_id)

    return unload_ok
