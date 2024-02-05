"""Support for generic GeoJSON events."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from aio_geojson_generic_client.feed_entry import GenericFeedEntry

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GeoJsonFeedEntityManager
from .const import (
    ATTR_EXTERNAL_ID,
    DOMAIN,
    SIGNAL_DELETE_ENTITY,
    SIGNAL_UPDATE_ENTITY,
    SOURCE,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the GeoJSON Events platform."""
    manager: GeoJsonFeedEntityManager = hass.data[DOMAIN][entry.entry_id]

    @callback
    def async_add_geolocation(
        feed_manager: GeoJsonFeedEntityManager,
        external_id: str,
    ) -> None:
        """Add geolocation entity from feed."""
        new_entity = GeoJsonLocationEvent(feed_manager, external_id)
        _LOGGER.debug("Adding geolocation %s", new_entity)
        async_add_entities([new_entity], True)

    manager.listeners.append(
        async_dispatcher_connect(hass, manager.signal_new_entity, async_add_geolocation)
    )
    # Do not wait for update here so that the setup can be completed and because an
    # update will fetch data from the feed via HTTP and then process that data.
    entry.async_create_task(hass, manager.async_update())
    _LOGGER.debug("Geolocation setup done")


class GeoJsonLocationEvent(GeolocationEvent):
    """Represents an external event with GeoJSON data."""

    _attr_should_poll = False
    _attr_source = SOURCE
    _attr_unit_of_measurement = UnitOfLength.KILOMETERS

    def __init__(
        self,
        feed_manager: GeoJsonFeedEntityManager,
        external_id: str,
    ) -> None:
        """Initialize entity with data from feed entry."""
        self._feed_manager = feed_manager
        self._external_id = external_id
        self._attr_unique_id = f"{feed_manager.entry_id}_{external_id}"
        self._remove_signal_delete: Callable[[], None]
        self._remove_signal_update: Callable[[], None]

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self._remove_signal_delete = async_dispatcher_connect(
            self.hass,
            SIGNAL_DELETE_ENTITY.format(self._external_id),
            self._delete_callback,
        )
        self._remove_signal_update = async_dispatcher_connect(
            self.hass,
            SIGNAL_UPDATE_ENTITY.format(self._external_id),
            self._update_callback,
        )

    @callback
    def _delete_callback(self) -> None:
        """Remove this entity."""
        self._remove_signal_delete()
        self._remove_signal_update()
        self.hass.async_create_task(self.async_remove(force_remove=True))

    @callback
    def _update_callback(self) -> None:
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        """Update this entity from the data held in the feed manager."""
        _LOGGER.debug("Updating %s", self._external_id)
        feed_entry = self._feed_manager.get_entry(self._external_id)
        if feed_entry:
            self._update_from_feed(feed_entry)

    def _update_from_feed(self, feed_entry: GenericFeedEntry) -> None:
        """Update the internal state from the provided feed entry."""
        if feed_entry.properties and "name" in feed_entry.properties:
            # The entry name's type can vary, but our own name must be a string
            self._attr_name = str(feed_entry.properties["name"])
        else:
            self._attr_name = feed_entry.title
        self._attr_distance = feed_entry.distance_to_home
        self._attr_latitude = feed_entry.coordinates[0]
        self._attr_longitude = feed_entry.coordinates[1]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        if not self._external_id:
            return {}
        return {ATTR_EXTERNAL_ID: self._external_id}
