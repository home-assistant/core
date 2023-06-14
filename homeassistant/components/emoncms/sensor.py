"""Platform for sensor integration."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import logging
from typing import Any

from homeassistant import config_entries
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .feed import Feed
from .hub import Hub

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add sensors for passed config_entry in HA."""
    hub: Hub = hass.data[DOMAIN][config_entry.entry_id]

    _LOGGER.info("Setting up entity %d", config_entry.entry_id)

    _LOGGER.info("  Getting feeds")
    feeds: list[Feed] = await hub.get_feeds()
    _LOGGER.info("  Got %d feeds", len(feeds))
    new_devices: list[FeedEntityValue] = []
    for feed in feeds:
        new_devices.append(FeedEntityValue(feed, hub))

    _LOGGER.info("  Adding %d entities asynchronously", len(new_devices))
    async_add_entities(new_devices)


class FeedEntityValue(SensorEntity):
    """An entity associated with a Hub and Feed, that provides the current value of the feed to Home Assistant."""

    _hub: Hub
    """The hub associated with the entity"""
    _feed: Feed
    """The feed associated with the entity"""

    def __init__(self, feed: Feed, hub: Hub) -> None:
        """Initialize the sensor."""
        self._feed = feed
        self._hub = hub

    @property
    def available(self) -> bool:
        """Checks whether the hub is currently available."""
        return self._hub.online

    @property
    def unique_id(self) -> str:
        """Return a unique ID to use for this entity."""
        return f"{self._hub.hub_id}/{self.name}/value"

    @property
    def name(self) -> str:
        """Returns the name of the feed."""
        return self._feed.name

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Returns the device class associated with the feed."""
        return self._feed.device_class

    @property
    def state_class(self) -> SensorStateClass | str | None:
        """Returns the state class associated with the feed."""
        return self._feed.state_class

    @property
    def native_unit_of_measurement(self) -> str:
        """Returns the unit specified by the feed."""
        return self._feed.unit

    @property
    def native_value(self) -> str | None:
        """Returns the processed value of the feed."""
        feed_value = self._feed.processed_value
        return str(feed_value) if feed_value is not None else None

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Provides some state attributes of the entity. This includes the time at which the feed has been updated."""
        return {"last_update": self._feed.last_update}

    async def async_update(self):
        """Update the currently stored value."""
        value: tuple[datetime | None, str] = await self._hub.fetch_feed_value(
            self._feed
        )
        self._feed.last_update = value[0]
        self._feed.raw_value = value[1]
