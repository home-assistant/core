"""Get a configured Growatt API."""
import logging

import growattServer

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .const import DEFAULT_URL, DEPRECATED_URLS

_LOGGER = logging.getLogger(__name__)


def get_configured_api(hass: HomeAssistant, config_entry: ConfigEntry):
    """Get and configure an API object."""

    config = {**config_entry.data}
    username = config[CONF_USERNAME]
    url = config.get(CONF_URL, DEFAULT_URL)

    # If the URL has been deprecated then change to the default instead
    if url in DEPRECATED_URLS:
        _LOGGER.info(
            "URL: %s has been deprecated, migrating to the latest default: %s",
            url,
            DEFAULT_URL,
        )
        url = DEFAULT_URL
        config[CONF_URL] = url
        hass.config_entries.async_update_entry(config_entry, data=config)

    # Initialise the library with the username & a random id each time it is started
    api = growattServer.GrowattApi(add_random_user_id=True, agent_identifier=username)
    api.server_url = url

    return api
