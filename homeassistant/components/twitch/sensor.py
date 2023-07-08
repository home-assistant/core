"""Support for the Twitch stream status."""
from __future__ import annotations

from twitchAPI.helper import first
from twitchAPI.twitch import (
    AuthType,
    InvalidTokenException,
    MissingScopeException,
    Twitch,
    TwitchAPIException,
    TwitchAuthorizationException,
    TwitchResourceNotFound,
    TwitchUser,
)
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_TOKEN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_CHANNELS, LOGGER, OAUTH_SCOPES

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_CLIENT_ID): cv.string,
        vol.Required(CONF_CLIENT_SECRET): cv.string,
        vol.Required(CONF_CHANNELS): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_TOKEN): cv.string,
    }
)


ATTR_GAME = "game"
ATTR_TITLE = "title"
ATTR_SUBSCRIPTION = "subscribed"
ATTR_SUBSCRIPTION_SINCE = "subscribed_since"
ATTR_SUBSCRIPTION_GIFTED = "subscription_is_gifted"
ATTR_FOLLOW = "following"
ATTR_FOLLOW_SINCE = "following_since"
ATTR_FOLLOWING = "followers"
ATTR_VIEWS = "views"

ICON = "mdi:twitch"

STATE_OFFLINE = "offline"
STATE_STREAMING = "streaming"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Twitch platform."""
    channels = config[CONF_CHANNELS]
    client_id = config[CONF_CLIENT_ID]
    client_secret = config[CONF_CLIENT_SECRET]
    oauth_token = config.get(CONF_TOKEN)

    try:
        client = await Twitch(
            app_id=client_id,
            app_secret=client_secret,
            target_app_auth_scope=OAUTH_SCOPES,
        )
        client.auto_refresh_auth = False
    except TwitchAuthorizationException:
        LOGGER.error("Invalid client ID or client secret")
        return

    if oauth_token:
        try:
            await client.set_user_authentication(
                token=oauth_token, scope=OAUTH_SCOPES, validate=True
            )
        except MissingScopeException:
            LOGGER.error("OAuth token is missing required scope")
            return
        except InvalidTokenException:
            LOGGER.error("OAuth token is invalid")
            return

    twitch_users: list[TwitchUser] = []
    async for channel in client.get_users(logins=channels):
        twitch_users.append(channel)

    async_add_entities(
        [TwitchSensor(channel, client) for channel in twitch_users],
        True,
    )


class TwitchSensor(SensorEntity):
    """Representation of a Twitch channel."""

    _attr_icon = ICON

    def __init__(self, channel: TwitchUser, client: Twitch) -> None:
        """Initialize the sensor."""
        self._client = client
        self._channel = channel
        self._enable_user_auth = client.has_required_auth(AuthType.USER, OAUTH_SCOPES)
        self._attr_name = channel.display_name
        self._attr_unique_id = channel.id

    async def async_update(self) -> None:
        """Update device state."""
        followers = (await self._client.get_users_follows(to_id=self._channel.id)).total
        self._attr_extra_state_attributes = {
            ATTR_FOLLOWING: followers,
            ATTR_VIEWS: self._channel.view_count,
        }
        if self._enable_user_auth:
            await self._async_add_user_attributes()
        if stream := (
            await first(self._client.get_streams(user_id=[self._channel.id], first=1))
        ):
            self._attr_native_value = STATE_STREAMING
            self._attr_extra_state_attributes[ATTR_GAME] = stream.game_name
            self._attr_extra_state_attributes[ATTR_TITLE] = stream.title
            self._attr_entity_picture = stream.thumbnail_url
            if self._attr_entity_picture is not None:
                self._attr_entity_picture = self._attr_entity_picture.format(
                    height=24,
                    width=24,
                )
        else:
            self._attr_native_value = STATE_OFFLINE
            self._attr_extra_state_attributes[ATTR_GAME] = None
            self._attr_extra_state_attributes[ATTR_TITLE] = None
            self._attr_entity_picture = self._channel.profile_image_url

    async def _async_add_user_attributes(self) -> None:
        if not (user := await first(self._client.get_users())):
            return
        self._attr_extra_state_attributes[ATTR_SUBSCRIPTION] = False
        try:
            sub = await self._client.check_user_subscription(
                user_id=user.id, broadcaster_id=self._channel.id
            )
            self._attr_extra_state_attributes[ATTR_SUBSCRIPTION] = True
            self._attr_extra_state_attributes[ATTR_SUBSCRIPTION_GIFTED] = sub.is_gift
        except TwitchResourceNotFound:
            LOGGER.debug("User is not subscribed")
        except TwitchAPIException as exc:
            LOGGER.error("Error response on check_user_subscription: %s", exc)

        follows = (
            await self._client.get_users_follows(
                from_id=user.id, to_id=self._channel.id
            )
        ).data
        self._attr_extra_state_attributes[ATTR_FOLLOW] = len(follows) > 0
        if len(follows):
            self._attr_extra_state_attributes[ATTR_FOLLOW_SINCE] = follows[
                0
            ].followed_at
