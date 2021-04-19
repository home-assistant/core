"""Integration with the Rachio Iro sprinkler system controller."""
import asyncio
import logging
import secrets

from rachiopy import Rachio
from requests.exceptions import ConnectTimeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv

from .const import CONF_CLOUDHOOK_URL, CONF_MANUAL_RUN_MINS, CONF_WEBHOOK_ID, DOMAIN
from .device import RachioPerson
from .webhooks import (
    async_get_or_create_registered_webhook_id_and_url,
    async_register_webhook,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "binary_sensor"]

CONFIG_SCHEMA = cv.deprecated(DOMAIN)


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
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_remove_entry(hass, entry):
    """Remove a rachio config entry."""
    if CONF_CLOUDHOOK_URL in entry.data:
        await hass.components.cloud.async_delete_cloudhook(entry.data[CONF_WEBHOOK_ID])


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
    rachio.webhook_auth = secrets.token_hex()
    webhook_id, webhook_url = await async_get_or_create_registered_webhook_id_and_url(
        hass, entry
    )
    rachio.webhook_url = webhook_url

    person = RachioPerson(rachio, entry)

    # Get the API user
    try:
        await person.async_setup(hass)
    except ConnectTimeout as error:
        _LOGGER.error("Could not reach the Rachio API: %s", error)
        raise ConfigEntryNotReady from error

    # Check for Rachio controller devices
    if not person.controllers:
        _LOGGER.error("No Rachio devices found in account %s", person.username)
        return False
    _LOGGER.info(
        "%d Rachio device(s) found; The url %s must be accessible from the internet in order to receive updates",
        len(person.controllers),
        webhook_url,
    )

    # Enable platform
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = person
    async_register_webhook(hass, webhook_id, entry.entry_id)

    for platform in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    return True
