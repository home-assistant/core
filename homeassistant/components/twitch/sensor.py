"""Support for the Twitch stream status."""
from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from . import TwitchDeviceEntity
from .const import DOMAIN
from .coordinator import TwitchUpdateCoordinator
from .data import TwitchCoordinatorData

ATTR_GAME = "game"
ATTR_TITLE = "title"
ATTR_SUBSCRIPTION = "subscribed"
ATTR_SUBSCRIPTION_GIFTED = "subscription_is_gifted"
ATTR_FOLLOWERS = "followers"
ATTR_FOLLOWING_SINCE = "following_since"
ATTR_VIEWS = "views"

STATE_OFFLINE = "offline"
STATE_STREAMING = "streaming"


@dataclass
class BaseEntityDescriptionMixin:
    """Mixin for required Twitch base description keys."""

    value_fn: Callable[[TwitchCoordinatorData, str], StateType]


@dataclass
class BaseEntityDescription(SensorEntityDescription):
    """Describes Twitch sensor entity default overrides."""

    icon: str = "mdi:twitch"
    available_fn: Callable[[TwitchCoordinatorData, str], bool] = lambda data, k: True
    attributes_fn: Callable[
        [TwitchCoordinatorData, str], Mapping[str, Any] | None
    ] = lambda data, k: None
    entity_picture_fn: Callable[
        [TwitchCoordinatorData, str], str | None
    ] = lambda data, k: None


@dataclass
class TwitchSensorEntityDescription(BaseEntityDescription, BaseEntityDescriptionMixin):
    """Describes Twitch issue sensor entity."""


def _twitch_channel_available(
    data: TwitchCoordinatorData,
    channel_id: str,
) -> bool:
    """Return True if the channel is available."""
    return (
        data.channels is not None
        and len(data.channels) > 0
        and next(
            (channel for channel in data.channels if channel.id == channel_id), None
        )
        is not None
    )


def _twitch_channel_attributes(
    data: TwitchCoordinatorData,
    channel_id: str,
) -> Mapping[str, Any]:
    """Return the attributes of the sensor."""
    if data.channels is None or len(data.channels) < 1:
        return {}
    channel = next(
        (channel for channel in data.channels if channel.id == channel_id), None
    )
    if channel is None:
        return {}

    return {
        ATTR_GAME: channel.stream.game_name if channel.stream is not None else None,
        ATTR_TITLE: channel.stream.title if channel.stream is not None else None,
        ATTR_SUBSCRIPTION: bool(channel.subscription),
        ATTR_SUBSCRIPTION_GIFTED: channel.subscription.is_gift
        if channel.subscription
        else None,
        ATTR_FOLLOWERS: channel.followers,
        ATTR_FOLLOWING_SINCE: channel.following.followed_at
        if channel.following
        else None,
        ATTR_VIEWS: channel.stream.viewer_count if channel.stream is not None else None,
    }


def _twitch_channel_entity_picture(
    data: TwitchCoordinatorData,
    channel_id: str,
) -> str | None:
    """Return the entity picture of the sensor."""
    if data.channels is None or len(data.channels) < 1:
        return None
    channel = next(
        (channel for channel in data.channels if channel.id == channel_id), None
    )
    if channel is None:
        return None

    if channel.stream is not None:
        if channel.stream.thumbnail_url is not None:
            return channel.stream.thumbnail_url.format(width=24, height=24)
    return channel.profile_image_url


def _twitch_channel_value(
    data: TwitchCoordinatorData,
    channel_id: str,
) -> StateType:
    """Return the value of the sensor."""
    if data.channels is None or len(data.channels) < 1:
        return None
    channel = next(
        (channel for channel in data.channels if channel.id == channel_id), None
    )
    if channel is None:
        return None

    if channel.stream is None:
        return STATE_OFFLINE
    return STATE_STREAMING


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Config entry example."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    data: TwitchCoordinatorData = coordinator.data

    entities: list[TwitchSensorEntity] = []

    for channel in data.channels:
        entities.append(
            TwitchSensorEntity(
                coordinator,
                TwitchSensorEntityDescription(
                    key=channel.id,
                    name=channel.display_name,
                    available_fn=_twitch_channel_available,
                    attributes_fn=_twitch_channel_attributes,
                    entity_picture_fn=_twitch_channel_entity_picture,
                    value_fn=_twitch_channel_value,
                ),
                channel.id,
                channel.display_name,
            )
        )

    async_add_entities(entities)


class TwitchSensorEntity(TwitchDeviceEntity, SensorEntity):
    """Define a Twitch sensor."""

    _attr_has_entity_name = False

    entity_description: TwitchSensorEntityDescription

    def __init__(
        self,
        coordinator: TwitchUpdateCoordinator,
        description: TwitchSensorEntityDescription,
        service_id: str,
        service_name: str,
    ) -> None:
        """Initialize sensor."""
        super().__init__(
            coordinator,
            service_id,
            service_name,
            description.key,
        )
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return (
            super().available
            and self.coordinator.data is not None
            and self.entity_description.available_fn(
                self.coordinator.data, self._service_id
            )
        )

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return self.entity_description.value_fn(self.coordinator.data, self._service_id)

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the extra state attributes."""
        return self.entity_description.attributes_fn(
            self.coordinator.data, self._service_id
        )

    @property
    def entity_picture(self) -> str | None:
        """Return the entity picture."""
        return self.entity_description.entity_picture_fn(
            self.coordinator.data, self._service_id
        )
