"""Integration with the Rachio Iro sprinkler system controller."""

import logging
import secrets

from rachiopy import Rachio
from requests.exceptions import ConnectTimeout

from homeassistant.components import cloud
from homeassistant.const import CONF_API_KEY, CONF_WEBHOOK_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from .const import CONF_CLOUDHOOK_URL, CONF_MANUAL_RUN_MINS
from .device import RachioConfigEntry, RachioPerson
from .webhooks import (
    async_get_or_create_registered_webhook_id_and_url,
    async_register_webhook,
    async_unregister_webhook,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.CALENDAR, Platform.SWITCH]


async def async_unload_entry(hass: HomeAssistant, entry: RachioConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        async_unregister_webhook(hass, entry)
    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: RachioConfigEntry) -> None:
    """Remove a rachio config entry."""
    if CONF_CLOUDHOOK_URL in entry.data:
        await cloud.async_delete_cloudhook(hass, entry.data[CONF_WEBHOOK_ID])


async def async_setup_entry(hass: HomeAssistant, entry: RachioConfigEntry) -> bool:
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
    try:
        webhook_url = await async_get_or_create_registered_webhook_id_and_url(
            hass, entry
        )
    except cloud.CloudNotConnected as exc:
        # User has an active cloud subscription, but the connection to the cloud is down
        raise ConfigEntryNotReady from exc
    rachio.webhook_url = webhook_url

    person = RachioPerson(rachio, entry)

    # Get the API user
    try:
        await person.async_setup(hass)
    except ConfigEntryAuthFailed as error:
        # Reauth is not yet implemented
        _LOGGER.error("Authentication failed: %s", error)
        return False
    except ConnectTimeout as error:
        _LOGGER.error("Could not reach the Rachio API: %s", error)
        raise ConfigEntryNotReady from error

    # Check for Rachio controller devices
    if not person.controllers and not person.base_stations:
        _LOGGER.error("No Rachio devices found in account %s", person.username)
        return False
    _LOGGER.debug(
        (
            "%d Rachio device(s) found; The url %s must be accessible from the internet"
            " in order to receive updates"
        ),
        len(person.controllers) + len(person.base_stations),
        webhook_url,
    )

    for base in person.base_stations:
        await base.status_coordinator.async_config_entry_first_refresh()
        await base.schedule_coordinator.async_config_entry_first_refresh()

    # Enable platform
    entry.runtime_data = person
    async_register_webhook(hass, entry)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True
