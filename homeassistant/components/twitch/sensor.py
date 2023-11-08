"""Support for the Twitch stream status."""
from __future__ import annotations

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

from .const import CONF_CHANNELS, DOMAIN
from .coordinator import TwitchChannelData, TwitchUpdateCoordinator

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
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data: dict[str, TwitchChannelData | None] = coordinator.data

    entities: list[TwitchSensor] = []
    for channel, channel_data in data.items():
        if channel_data is None:
            raise ValueError(f"Channel {channel} not found on initialization")

        entities.append(
            TwitchSensor(
                coordinator,
                channel_data.user.id,
                channel_data.user.display_name,
                channel,
            )
        )

    async_add_entities(entities, True)


class TwitchSensor(SensorEntity):
    """Representation of a Twitch channel."""

    _attr_icon = ICON

    def __init__(
        self,
        coordinator: TwitchUpdateCoordinator,
        key: str,
        name: str,
        channel: str,
    ) -> None:
        """Initialize the sensor."""
        self.coordinator = coordinator
        self._key = key
        self._attr_name = name
        self._attr_unique_id = key
        self._channel = channel

    async def async_update(self) -> None:
        """Update device state."""
        channel_data = self.coordinator.data[self._channel]
        if channel_data is None:
            raise ValueError(f"Channel {self._channel} not found on update")

        self._attr_extra_state_attributes = {
            ATTR_FOLLOWING: channel_data.followers,
            ATTR_VIEWS: channel_data.user.view_count,
        }
        if channel_data.stream:
            self._attr_native_value = STATE_STREAMING
            self._attr_extra_state_attributes[ATTR_GAME] = channel_data.stream.game_name
            self._attr_extra_state_attributes[ATTR_TITLE] = channel_data.stream.title
            self._attr_entity_picture = channel_data.stream.thumbnail_url
            if self._attr_entity_picture is not None:
                self._attr_entity_picture = self._attr_entity_picture.format(
                    height=24,
                    width=24,
                )
        else:
            self._attr_native_value = STATE_OFFLINE
            self._attr_extra_state_attributes[ATTR_GAME] = None
            self._attr_extra_state_attributes[ATTR_TITLE] = None
            self._attr_entity_picture = channel_data.user.profile_image_url

        self._attr_extra_state_attributes[ATTR_SUBSCRIPTION] = (
            channel_data.subscription is not None
        )
        self._attr_extra_state_attributes[ATTR_SUBSCRIPTION_GIFTED] = (
            channel_data.subscription.is_gift if channel_data.subscription else None
        )

        self._attr_extra_state_attributes[ATTR_FOLLOW] = (
            channel_data.following.total > 0
            if channel_data.following is not None
            else None
        )
        self._attr_extra_state_attributes[ATTR_FOLLOW_SINCE] = (
            channel_data.following.data[0].followed_at
            if channel_data.following is not None
            and len(channel_data.following.data) > 0
            else None
        )
