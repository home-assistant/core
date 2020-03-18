"""Support for the Twitch stream status."""
import logging

from requests.exceptions import HTTPError
from twitch import TwitchClient
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.const import ATTR_FRIENDLY_NAME, CONF_TOKEN
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

ATTR_GAME = "game"
ATTR_TITLE = "title"
ATTR_SUBSCRIPTION = "subscribed"
ATTR_SUBSCRIPTION_SINCE = "subscribed_since"
ATTR_SUBSCRIPTION_GIFTED = "subscription_is_gifted"
ATTR_FOLLOW = "following"
ATTR_FOLLOW_SINCE = "following_since"
ATTR_FOLLOWING = "followers"
ATTR_VIEWS = "views"

CONF_CHANNELS = "channels"
CONF_CLIENT_ID = "client_id"

ICON = "mdi:twitch"

STATE_OFFLINE = "offline"
STATE_STREAMING = "streaming"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CHANNELS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_TOKEN): cv.string,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the Twitch platform."""
    channels = config[CONF_CHANNELS]
    client_id = config[CONF_CLIENT_ID]
    oauth_token = config.get(CONF_TOKEN)
    client = TwitchClient(client_id, oauth_token)

    try:
        client.ingests.get_server_list()
    except HTTPError:
        _LOGGER.error("Client ID or OAuth token is not valid")
        return

    channel_ids = client.users.translate_usernames_to_ids(channels)

    add_entities([TwitchSensor(channel_id, client) for channel_id in channel_ids], True)


class TwitchSensor(Entity):
    """Representation of an Twitch channel."""

    def __init__(self, channel, client):
        """Initialize the sensor."""
        self._client = client
        self._channel = channel
        self._oauth_enabled = client._oauth_token is not None
        self._state = None
        self._preview = None
        self._game = None
        self._title = None
        self._subscription = None
        self._follow = None
        self._statistics = None

    @property
    def should_poll(self):
        """Device should be polled."""
        return True

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._channel.display_name

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
        attr = {
            ATTR_FRIENDLY_NAME: self._channel.display_name,
        }
        attr.update(self._statistics)

        if self._oauth_enabled:
            attr.update(self._subscription)
            attr.update(self._follow)

        if self._state == STATE_STREAMING:
            attr.update({ATTR_GAME: self._game, ATTR_TITLE: self._title})
        return attr

    @property
    def unique_id(self):
        """Return unique ID for this sensor."""
        return self._channel.id

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Update device state."""

        channel = self._client.channels.get_by_id(self._channel.id)

        self._statistics = {
            ATTR_FOLLOWING: channel.followers,
            ATTR_VIEWS: channel.views,
        }
        if self._oauth_enabled:
            user = self._client.users.get()

            try:
                sub = self._client.users.check_subscribed_to_channel(
                    user.id, self._channel.id
                )
                self._subscription = {
                    ATTR_SUBSCRIPTION: True,
                    ATTR_SUBSCRIPTION_SINCE: sub.created_at,
                    ATTR_SUBSCRIPTION_GIFTED: sub.is_gift,
                }
            except HTTPError:
                self._subscription = {ATTR_SUBSCRIPTION: False}

            try:
                follow = self._client.users.check_follows_channel(
                    user.id, self._channel.id
                )
                self._follow = {ATTR_FOLLOW: True, ATTR_FOLLOW_SINCE: follow.created_at}
            except HTTPError:
                self._follow = {ATTR_FOLLOW: False}

        stream = self._client.streams.get_stream_by_user(self._channel.id)
        if stream:
            self._game = stream.channel.get("game")
            self._title = stream.channel.get("status")
            self._preview = stream.preview.get("medium")
            self._state = STATE_STREAMING
        else:
            self._preview = self._channel.logo
            self._state = STATE_OFFLINE
