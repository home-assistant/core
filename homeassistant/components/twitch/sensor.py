"""Support for the Twitch stream status."""
from __future__ import annotations

import logging

from twitchAPI.twitch import (
    AuthScope,
    InvalidTokenException,
    MissingScopeException,
    Twitch,
    TwitchAuthorizationException,
)
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_TOKEN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

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

ICON = "mdi:twitch"

STATE_OFFLINE = "offline"
STATE_STREAMING = "streaming"

OAUTH_SCOPES = [AuthScope.USER_READ_SUBSCRIPTIONS]

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Required(CONF_CHANNELS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_TOKEN): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Twitch platform."""
    channels = config[CONF_CHANNELS]
    client_id = config[CONF_CLIENT_ID]
    client_secret = config[CONF_CLIENT_SECRET]
    oauth_token = config.get(CONF_TOKEN)
    client = Twitch(app_id=client_id, app_secret=client_secret)
    client.auto_refresh_auth = False

    try:
        client.authenticate_app(scope=OAUTH_SCOPES)
    except TwitchAuthorizationException:
        _LOGGER.error("INvalid client ID or client secret")
        return

    if oauth_token:
        try:
            client.set_user_authentication(
                token=oauth_token, scope=OAUTH_SCOPES, validate=True
            )
        except MissingScopeException:
            _LOGGER.error("OAuth token is missing required scope")
            return
        except InvalidTokenException:
            _LOGGER.error("OAuth token is invalid")
            return

    channels = client.get_users(logins=channels)

    add_entities(
        [
            TwitchSensor(
                channel=channel, client=client, enable_user_auth=bool(oauth_token)
            )
            for channel in channels["data"]
        ],
        True,
    )


class TwitchSensor(SensorEntity):
    """Representation of an Twitch channel."""

    def __init__(self, channel, client: Twitch, enable_user_auth: bool):
        """Initialize the sensor."""
        self._client = client
        self._channel = channel
        self._enable_user_auth = enable_user_auth
        self._state = None
        self._preview = None
        self._game = None
        self._title = None
        self._subscription = None
        self._follow = None
        self._statistics = None

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._channel["display_name"]

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def entity_picture(self):
        """Return preview of current game."""
        return self._preview

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        attr = dict(self._statistics)

        if self._enable_user_auth:
            attr.update(self._subscription)
            attr.update(self._follow)

        if self._state == STATE_STREAMING:
            attr.update({ATTR_GAME: self._game, ATTR_TITLE: self._title})
        return attr

    @property
    def unique_id(self):
        """Return unique ID for this sensor."""
        return self._channel["id"]

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return ICON

    def update(self):
        """Update device state."""

        followers = self._client.get_users_follows(to_id=self._channel["id"])["total"]
        channel = self._client.get_users(user_ids=[self._channel["id"]])["data"][0]

        self._statistics = {
            ATTR_FOLLOWING: followers,
            ATTR_VIEWS: channel["view_count"],
        }
        if self._enable_user_auth:
            user = self._client.get_users()["data"][0]

            sub = self._client.check_user_subscription(
                user_id=user["id"], broadcaster_id=self._channel["id"]
            )
            if sub["status"] == 200:
                self._subscription = {
                    ATTR_SUBSCRIPTION: True,
                    ATTR_SUBSCRIPTION_GIFTED: sub["data"]["is_gift"],
                }
            elif sub["status"] == 404:
                self._subscription = {ATTR_SUBSCRIPTION: False}
            else:
                raise Exception(
                    f"Error response on check_user_subscription: {sub['error']}"
                )

            follows = self._client.get_users_follows(
                from_id=user["id"], to_id=self._channel["id"]
            )["data"]
            if len(follows) > 0:
                self._follow = {
                    ATTR_FOLLOW: True,
                    ATTR_FOLLOW_SINCE: follows[0]["followed_at"],
                }
            else:
                self._follow = {ATTR_FOLLOW: False}

        streams = self._client.get_streams(user_id=[self._channel["id"]])["data"]
        if len(streams) > 0:
            stream = streams[0]
            self._game = stream["game_name"]
            self._title = stream["title"]
            self._preview = stream["thumbnail_url"]
            self._state = STATE_STREAMING
        else:
            self._preview = channel["offline_image_url"]
            self._state = STATE_OFFLINE
