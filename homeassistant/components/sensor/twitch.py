"""
Support for the Twitch stream status.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/sensor.twitch/
"""
import logging

import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv

REQUIREMENTS = ['python-twitch-client==0.6.0']

_LOGGER = logging.getLogger(__name__)

ATTR_GAME = 'game'
ATTR_TITLE = 'title'

CONF_CHANNELS = 'channels'
CONF_CLIENT_ID = 'client_id'
ICON = 'mdi:twitch'

STATE_OFFLINE = 'offline'
STATE_STREAMING = 'streaming'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_CLIENT_ID): cv.string,
    vol.Required(CONF_CHANNELS, default=[]):
        vol.All(cv.ensure_list, [cv.string]),
})


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Twitch platform."""
    from twitch import TwitchClient
    from requests.exceptions import HTTPError

    channels = config.get(CONF_CHANNELS, [])
    client = TwitchClient(client_id=config.get(CONF_CLIENT_ID))

    try:
        client.ingests.get_server_list()
    except HTTPError:
        _LOGGER.error("Client ID is not valid")
        return

    users = client.users.translate_usernames_to_ids(channels)

    add_entities([TwitchSensor(user, client) for user in users], True)


class TwitchSensor(Entity):
    """Representation of an Twitch channel."""

    def __init__(self, user, client):
        """Initialize the sensor."""
        self._client = client
        self._user = user
        self._channel = self._user.name
        self._id = self._user.id
        self._state = STATE_OFFLINE
        self._preview = self._game = self._title = None

    @property
    def should_poll(self):
        """Device should be polled."""
        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._channel

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def entity_picture(self):
        """Return preview of current game."""
        return self._preview

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        if self._state == STATE_STREAMING:
            return {
                ATTR_GAME: self._game,
                ATTR_TITLE: self._title,
            }

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    # pylint: disable=no-member
    def update(self):
        """Update device state."""
        stream = self._client.streams.get_stream_by_user(self._id)
        if stream:
            self._game = stream.get('channel').get('game')
            self._title = stream.get('channel').get('status')
            self._preview = stream.get('preview').get('medium')
            self._state = STATE_STREAMING
        else:
            self._preview = self._client.users.get_by_id(self._id).get('logo')
            self._state = STATE_OFFLINE
