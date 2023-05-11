"""Support for the Twitch stream status."""
from __future__ import annotations

import logging

from twitchAPI.twitch import (
    AuthType,
    InvalidTokenException,
    MissingScopeException,
    Twitch,
    TwitchAuthorizationException,
)

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import CONF_CHANNELS, DOMAIN, OAUTH_SCOPES

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

ICON = "mdi:twitch"

STATE_OFFLINE = "offline"
STATE_STREAMING = "streaming"


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Import the legacy YAML configuration and log a warning message."""
    async_create_issue(
        hass,
        DOMAIN,
        "deprecated_yaml",
        breaks_in_ha_version="2023.8.0",
        is_fixable=False,
        severity=IssueSeverity.WARNING,
        translation_key="deprecated_yaml",
    )

    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=config,
        )
    )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Twitch platform."""
    try:
        sensors: list[TwitchSensor] = await hass.async_add_executor_job(_setup, entry)
        async_add_entities(sensors, True)
    except MissingScopeException:
        _LOGGER.error("OAuth token is missing required scope")
        return
    except TwitchAuthorizationException:
        _LOGGER.error("Invalid client ID or client secret")
        return
    except InvalidTokenException:
        _LOGGER.error("OAuth token is invalid")
        return


def _setup(entry: ConfigEntry) -> list[TwitchSensor]:
    client_id: str = entry.data[CONF_CLIENT_ID]
    client_secret: str = entry.data[CONF_CLIENT_SECRET]
    oauth_token: str | None = entry.data.get(CONF_TOKEN)

    channels: str | None = entry.options.get(CONF_CHANNELS)

    if not channels:
        return []

    channels_list = channels.strip().split(",")

    client = Twitch(
        app_id=client_id,
        app_secret=client_secret,
        target_app_auth_scope=OAUTH_SCOPES,
    )

    client.auto_refresh_auth = False

    if oauth_token:
        client.set_user_authentication(
            token=oauth_token, scope=OAUTH_SCOPES, validate=True
        )

    channels_result: dict = client.get_users(logins=channels_list)
    return [TwitchSensor(channel, client) for channel in channels_result["data"]]


class TwitchSensor(SensorEntity):
    """Representation of an Twitch channel."""

    _attr_icon = ICON

    def __init__(self, channel: dict[str, str], client: Twitch) -> None:
        """Initialize the sensor."""
        self._client = client
        self._enable_user_auth = client.has_required_auth(AuthType.USER, OAUTH_SCOPES)
        self._attr_name = channel["display_name"]
        self._attr_unique_id = channel["id"]

    def update(self) -> None:
        """Update device state."""
        followers = self._client.get_users_follows(to_id=self.unique_id)["total"]
        channel = self._client.get_users(user_ids=[self.unique_id])["data"][0]
        self._attr_extra_state_attributes = {
            ATTR_FOLLOWING: followers,
            ATTR_VIEWS: channel["view_count"],
        }
        if self._enable_user_auth:
            user = self._client.get_users()["data"][0]["id"]

            subs = self._client.check_user_subscription(
                user_id=user, broadcaster_id=self.unique_id
            )
            if "data" in subs:
                self._attr_extra_state_attributes[ATTR_SUBSCRIPTION] = True
                self._attr_extra_state_attributes[ATTR_SUBSCRIPTION_GIFTED] = subs[
                    "data"
                ][0]["is_gift"]
            elif "status" in subs and subs["status"] == 404:
                self._attr_extra_state_attributes[ATTR_SUBSCRIPTION] = False
            elif "error" in subs:
                _LOGGER.error(
                    "Error response on check_user_subscription: %s", subs["error"]
                )
                return
            else:
                _LOGGER.error("Unknown error response on check_user_subscription")
                return

            follows = self._client.get_users_follows(
                from_id=user, to_id=self.unique_id
            )["data"]
            self._attr_extra_state_attributes[ATTR_FOLLOW] = len(follows) > 0
            if len(follows):
                self._attr_extra_state_attributes[ATTR_FOLLOW_SINCE] = follows[0][
                    "followed_at"
                ]

        if streams := self._client.get_streams(user_id=[self.unique_id])["data"]:
            stream = streams[0]
            self._attr_native_value = STATE_STREAMING
            self._attr_extra_state_attributes[ATTR_GAME] = stream["game_name"]
            self._attr_extra_state_attributes[ATTR_TITLE] = stream["title"]
            self._attr_entity_picture = stream["thumbnail_url"]
            if self._attr_entity_picture is not None:
                self._attr_entity_picture = self._attr_entity_picture.format(
                    height=24,
                    width=24,
                )
        else:
            self._attr_native_value = STATE_OFFLINE
            self._attr_extra_state_attributes[ATTR_GAME] = None
            self._attr_extra_state_attributes[ATTR_TITLE] = None
            self._attr_entity_picture = channel["profile_image_url"]
