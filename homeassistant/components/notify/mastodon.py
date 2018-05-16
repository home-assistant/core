"""
Mastodon platform for notify component.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/notify.mastodon/
"""
import logging

import voluptuous as vol

from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService)
from homeassistant.const import CONF_ACCESS_TOKEN
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['Mastodon.py==1.2.2']

_LOGGER = logging.getLogger(__name__)

CONF_BASE_URL = 'base_url'
CONF_CLIENT_ID = 'client_id'
CONF_CLIENT_SECRET = 'client_secret'

DEFAULT_URL = 'https://mastodon.social'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Required(CONF_CLIENT_ID): cv.string,
    vol.Required(CONF_CLIENT_SECRET): cv.string,
    vol.Optional(CONF_BASE_URL, default=DEFAULT_URL): cv.string,
})


def get_service(hass, config, discovery_info=None):
    """Get the Mastodon notification service."""
    from mastodon import Mastodon
    from mastodon.Mastodon import MastodonUnauthorizedError

    client_id = config.get(CONF_CLIENT_ID)
    client_secret = config.get(CONF_CLIENT_SECRET)
    access_token = config.get(CONF_ACCESS_TOKEN)
    base_url = config.get(CONF_BASE_URL)

    try:
        mastodon = Mastodon(
            client_id=client_id, client_secret=client_secret,
            access_token=access_token, api_base_url=base_url)
        mastodon.account_verify_credentials()
    except MastodonUnauthorizedError:
        _LOGGER.warning("Authentication failed")
        return None

    return MastodonNotificationService(mastodon)


class MastodonNotificationService(BaseNotificationService):
    """Implement the notification service for Mastodon."""

    def __init__(self, api):
        """Initialize the service."""
        self._api = api

    def send_message(self, message="", **kwargs):
        """Send a message to a user."""
        from mastodon.Mastodon import MastodonAPIError

        try:
            self._api.toot(message)
        except MastodonAPIError:
            _LOGGER.error("Unable to send message")
