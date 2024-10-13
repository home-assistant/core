"""Support for the Twitch stream status."""

from __future__ import annotations

from twitchAPI.helper import first
from twitchAPI.twitch import (
    AuthType,
    Twitch,
    TwitchAPIException,
    TwitchResourceNotFound,
    TwitchUser,
)

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.config_entry_oauth2_flow import OAuth2Session
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CLIENT, CONF_CHANNELS, DOMAIN, LOGGER, OAUTH_SCOPES, SESSION

ATTR_GAME = "game"
ATTR_TITLE = "title"
ATTR_SUBSCRIPTION = "subscribed"
ATTR_SUBSCRIPTION_SINCE = "subscribed_since"
ATTR_SUBSCRIPTION_GIFTED = "subscription_is_gifted"
ATTR_FOLLOW = "following"
ATTR_FOLLOW_SINCE = "following_since"
ATTR_FOLLOWING = "followers"
ATTR_VIEWS = "views"
ATTR_STARTED_AT = "started_at"

STATE_OFFLINE = "offline"
STATE_STREAMING = "streaming"

PARALLEL_UPDATES = 1


def chunk_list(lst: list, chunk_size: int) -> list[list]:
    """Split a list into chunks of chunk_size."""
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize entries."""
    client = hass.data[DOMAIN][entry.entry_id][CLIENT]
    session = hass.data[DOMAIN][entry.entry_id][SESSION]

    channels = entry.options[CONF_CHANNELS]

    entities: list[TwitchSensor] = []

    # Split channels into chunks of 100 to avoid hitting the rate limit
    for chunk in chunk_list(channels, 100):
        entities.extend(
            [
                TwitchSensor(channel, session, client)
                async for channel in client.get_users(logins=chunk)
            ]
        )

    async_add_entities(entities, True)


class TwitchSensor(SensorEntity):
    """Representation of a Twitch channel."""

    _attr_translation_key = "channel"

    def __init__(
        self, channel: TwitchUser, session: OAuth2Session, client: Twitch
    ) -> None:
        """Initialize the sensor."""
        self._session = session
        self._client = client
        self._channel = channel
        self._enable_user_auth = client.has_required_auth(AuthType.USER, OAUTH_SCOPES)
        self._attr_name = channel.display_name
        self._attr_unique_id = channel.id

    async def async_update(self) -> None:
        """Update device state."""
        await self._session.async_ensure_token_valid()
        await self._client.set_user_authentication(
            self._session.token["access_token"],
            OAUTH_SCOPES,
            self._session.token["refresh_token"],
            False,
        )
        followers = await self._client.get_channel_followers(self._channel.id)

        self._attr_extra_state_attributes = {
            ATTR_FOLLOWING: followers.total,
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
            self._attr_extra_state_attributes[ATTR_STARTED_AT] = stream.started_at
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
            self._attr_extra_state_attributes[ATTR_STARTED_AT] = None
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
            LOGGER.debug("User is not subscribed to %s", self._channel.display_name)
        except TwitchAPIException as exc:
            LOGGER.error("Error response on check_user_subscription: %s", exc)

        follows = await self._client.get_followed_channels(
            user.id, broadcaster_id=self._channel.id
        )
        self._attr_extra_state_attributes[ATTR_FOLLOW] = follows.total > 0
        if follows.total:
            self._attr_extra_state_attributes[ATTR_FOLLOW_SINCE] = follows.data[
                0
            ].followed_at
