"""Integration with the Rachio Iro sprinkler system controller."""
import asyncio
import logging
import secrets

from rachiopy import Rachio
import voluptuous as vol

from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_CUSTOM_URL,
    CONF_MANUAL_RUN_MINS,
    DEFAULT_MANUAL_RUN_MINS,
    DOMAIN,
    RACHIO_API_EXCEPTIONS,
)
from .device import RachioPerson
from .webhooks import WEBHOOK_PATH, RachioWebhookView

_LOGGER = logging.getLogger(__name__)

SUPPORTED_DOMAINS = ["switch", "binary_sensor"]

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_API_KEY): cv.string,
                vol.Optional(CONF_CUSTOM_URL): cv.string,
                vol.Optional(
                    CONF_MANUAL_RUN_MINS, default=DEFAULT_MANUAL_RUN_MINS
                ): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the rachio component from YAML."""

    conf = config.get(DOMAIN)
    hass.data.setdefault(DOMAIN, {})

    if not conf:
        return True

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload a config entry."""
    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, component)
                for component in SUPPORTED_DOMAINS
            ]
        )
    )

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up the Rachio config entry."""

    config = entry.data
    options = entry.options

    # CONF_MANUAL_RUN_MINS can only come from a yaml import
    if not options.get(CONF_MANUAL_RUN_MINS) and config.get(CONF_MANUAL_RUN_MINS):
        options_copy = options.copy()
        options_copy[CONF_MANUAL_RUN_MINS] = config[CONF_MANUAL_RUN_MINS]
        hass.config_entries.async_update_entry(entry, options=options_copy)

    # Configure API
    api_key = config[CONF_API_KEY]
    rachio = Rachio(api_key)

    # Get the URL of this server
    custom_url = config.get(CONF_CUSTOM_URL)
    hass_url = hass.config.api.base_url if custom_url is None else custom_url
    rachio.webhook_auth = secrets.token_hex()
    webhook_url_path = f"{WEBHOOK_PATH}-{entry.entry_id}"
    rachio.webhook_url = f"{hass_url}{webhook_url_path}"

    person = RachioPerson(rachio, entry)

    # Get the API user
    try:
        await hass.async_add_executor_job(person.setup, hass)
    # Yes we really do get all these exceptions (hopefully rachiopy switches to requests)
    # and there is not a reasonable timeout here so it can block for a long time
    except RACHIO_API_EXCEPTIONS as error:
        _LOGGER.error("Could not reach the Rachio API: %s", error)
        raise ConfigEntryNotReady

    # Check for Rachio controller devices
    if not person.controllers:
        _LOGGER.error("No Rachio devices found in account %s", person.username)
        return False
    _LOGGER.info("%d Rachio device(s) found", len(person.controllers))

    # Enable component
    hass.data[DOMAIN][entry.entry_id] = person

    # Listen for incoming webhook connections after the data is there
    hass.http.register_view(RachioWebhookView(entry.entry_id, webhook_url_path))

    for component in SUPPORTED_DOMAINS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    return True
