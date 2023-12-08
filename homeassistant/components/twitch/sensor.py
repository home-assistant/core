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
import voluptuous as vol

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_CLIENT_ID, CONF_CLIENT_SECRET, CONF_TOKEN
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.issue_registry import IssueSeverity, async_create_issue
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import CONF_CHANNELS, DOMAIN, LOGGER, OAUTH_SCOPES

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


def chunk_list(lst: list, chunk_size: int) -> list[list]:
    """Split a list into chunks of chunk_size."""
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Twitch platform."""
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(config[CONF_CLIENT_ID], config[CONF_CLIENT_SECRET]),
    )
    if CONF_TOKEN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": SOURCE_IMPORT}, data=config
            )
        )
    else:
        async_create_issue(
            hass,
            DOMAIN,
            "deprecated_yaml_credentials_imported",
            breaks_in_ha_version="2024.4.0",
            is_fixable=False,
            severity=IssueSeverity.WARNING,
            translation_key="deprecated_yaml_credentials_imported",
            translation_placeholders={
                "domain": DOMAIN,
                "integration_title": "Twitch",
            },
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Initialize entries."""
    client = hass.data[DOMAIN][entry.entry_id]

    channels = entry.options[CONF_CHANNELS]

    entities: list[TwitchSensor] = []

    # Split channels into chunks of 100 to avoid hitting the rate limit
    for chunk in chunk_list(channels, 100):
        entities.extend(
            [
                TwitchSensor(channel, client)
                async for channel in client.get_users(logins=chunk)
            ]
        )

    async_add_entities(entities, True)


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
        followers = (await self._client.get_channel_followers(self._channel.id)).total
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

        follows = await self._client.get_followed_channels(
            user.id, broadcaster_id=self._channel.id
        )
        self._attr_extra_state_attributes[ATTR_FOLLOW] = follows.total > 0
        if follows.total:
            self._attr_extra_state_attributes[ATTR_FOLLOW_SINCE] = follows.data[
                0
            ].followed_at
