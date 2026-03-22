"""Support for the Twitch stream status."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.typing import StateType
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CLEANUP_UNFOLLOWED
from .coordinator import TwitchConfigEntry, TwitchCoordinator, TwitchUpdate

ATTR_GAME = "game"
ATTR_TITLE = "title"
ATTR_SUBSCRIPTION = "subscribed"
ATTR_SUBSCRIPTION_GIFTED = "subscription_is_gifted"
ATTR_SUBSCRIPTION_TIER = "subscription_tier"
ATTR_FOLLOW = "following"
ATTR_FOLLOW_SINCE = "following_since"
ATTR_FOLLOWING = "followers"
ATTR_VIEWERS = "viewers"
ATTR_STARTED_AT = "started_at"
ATTR_CHANNEL_PICTURE = "channel_picture"

STATE_OFFLINE = "offline"
STATE_STREAMING = "streaming"

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: TwitchConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Initialize entries."""
    coordinator = entry.runtime_data
    known_channel_ids: set[str] = set()

    @callback
    def _async_add_new_entities() -> None:
        """Add sensor entities for new channels and remove unfollowed ones."""
        current_ids = set(coordinator.data)
        new_ids = current_ids - known_channel_ids
        if new_ids:
            known_channel_ids.update(new_ids)
            async_add_entities(
                TwitchSensor(coordinator, channel_id) for channel_id in sorted(new_ids)
            )
        if entry.options.get(CONF_CLEANUP_UNFOLLOWED, False):
            removed_ids = known_channel_ids - current_ids
            if removed_ids:
                known_channel_ids.difference_update(removed_ids)
                entity_registry = er.async_get(hass)
                for entity_entry in er.async_entries_for_config_entry(
                    entity_registry, entry.entry_id
                ):
                    if (
                        entity_entry.domain == "sensor"
                        and entity_entry.unique_id in removed_ids
                    ):
                        entity_registry.async_remove(entity_entry.entity_id)

    # Remove stale entity registry entries left from a previous session
    # (e.g. channels unfollowed while HA was offline).
    if entry.options.get(CONF_CLEANUP_UNFOLLOWED, False):
        entity_registry = er.async_get(hass)
        current_channel_ids = set(coordinator.data)
        for entity_entry in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if (
                entity_entry.domain == "sensor"
                and entity_entry.unique_id not in current_channel_ids
            ):
                entity_registry.async_remove(entity_entry.entity_id)

    # Create entities for channels already known after first refresh.
    _async_add_new_entities()
    # On subsequent coordinator updates, add new / remove unfollowed entities.
    entry.async_on_unload(coordinator.async_add_listener(_async_add_new_entities))


class TwitchSensor(CoordinatorEntity[TwitchCoordinator], SensorEntity):
    """Representation of a Twitch channel."""

    _attr_translation_key = "channel"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [STATE_OFFLINE, STATE_STREAMING]

    def __init__(self, coordinator: TwitchCoordinator, channel_id: str) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.channel_id = channel_id
        self._attr_unique_id = channel_id
        self._attr_name = self.channel.name

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.channel_id in self.coordinator.data

    @property
    def channel(self) -> TwitchUpdate:
        """Return the channel data."""
        return self.coordinator.data[self.channel_id]

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return STATE_STREAMING if self.channel.is_streaming else STATE_OFFLINE

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        channel = self.channel
        resp = {
            ATTR_FOLLOWING: channel.followers,
            ATTR_GAME: channel.game,
            ATTR_TITLE: channel.title,
            ATTR_STARTED_AT: channel.started_at,
            ATTR_VIEWERS: channel.viewers,
            ATTR_SUBSCRIPTION: False,
            ATTR_CHANNEL_PICTURE: channel.picture,
        }
        if channel.subscribed is not None:
            resp[ATTR_SUBSCRIPTION] = channel.subscribed
            resp[ATTR_SUBSCRIPTION_GIFTED] = channel.subscription_gifted
            resp[ATTR_SUBSCRIPTION_TIER] = channel.subscription_tier
        resp[ATTR_FOLLOW] = channel.follows
        if channel.follows:
            resp[ATTR_FOLLOW_SINCE] = channel.following_since
        return resp

    @property
    def entity_picture(self) -> str | None:
        """Return the picture of the sensor."""
        if self.channel_id not in self.coordinator.data:
            return None
        if self.channel.is_streaming:
            assert self.channel.stream_picture is not None
            return self.channel.stream_picture
        return self.channel.picture
