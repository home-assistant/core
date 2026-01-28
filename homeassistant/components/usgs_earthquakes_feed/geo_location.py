"""Support for U.S. Geological Survey Earthquake Hazards Program Feeds."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from aio_geojson_usgs_earthquakes.feed_entry import (
    UsgsEarthquakeHazardsProgramFeedEntry,
)

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.const import ATTR_TIME, UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UsgsEarthquakesFeedConfigEntry, UsgsEarthquakesFeedEntityManager

_LOGGER = logging.getLogger(__name__)

ATTR_ALERT = "alert"
ATTR_EXTERNAL_ID = "external_id"
ATTR_MAGNITUDE = "magnitude"
ATTR_PLACE = "place"
ATTR_STATUS = "status"
ATTR_TYPE = "type"
ATTR_UPDATED = "updated"

DEFAULT_UNIT_OF_MEASUREMENT = UnitOfLength.KILOMETERS

SOURCE = "usgs_earthquakes_feed"


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UsgsEarthquakesFeedConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the USGS Earthquakes Feed platform from config entry."""
    manager = entry.runtime_data

    @callback
    def async_add_geolocation(
        manager: UsgsEarthquakesFeedEntityManager,
        integration_id: str | None,
        external_id: str,
    ) -> None:
        """Add geolocation entity from feed."""
        new_entity = UsgsEarthquakesEvent(manager, integration_id, external_id)
        async_add_entities([new_entity], True)

    manager.listeners.append(
        async_dispatcher_connect(
            hass, manager.async_event_new_entity(), async_add_geolocation
        )
    )

    _LOGGER.debug("Geolocation setup completed")

    # Get first update
    await manager.async_update()


class UsgsEarthquakesEvent(GeolocationEvent):
    """Represents an external event with USGS Earthquake data."""

    _attr_icon = "mdi:pulse"
    _attr_should_poll = False
    _attr_source = SOURCE
    _attr_unit_of_measurement = DEFAULT_UNIT_OF_MEASUREMENT

    def __init__(
        self,
        feed_manager: UsgsEarthquakesFeedEntityManager,
        integration_id: str | None,
        external_id: str,
    ) -> None:
        """Initialize entity with data from feed entry."""
        self._feed_manager = feed_manager
        self._integration_id = integration_id
        self._external_id = external_id
        self._place = None
        self._magnitude = None
        self._time = None
        self._updated = None
        self._status = None
        self._type = None
        self._alert = None
        self._remove_signal_delete: Callable[[], None]
        self._remove_signal_update: Callable[[], None]

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self._remove_signal_delete = async_dispatcher_connect(
            self.hass,
            f"usgs_earthquakes_feed_delete_{self._external_id}",
            self._delete_callback,
        )
        self._remove_signal_update = async_dispatcher_connect(
            self.hass,
            f"usgs_earthquakes_feed_update_{self._external_id}",
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

    def _update_from_feed(
        self, feed_entry: UsgsEarthquakeHazardsProgramFeedEntry
    ) -> None:
        """Update the internal state from the provided feed entry."""
        self._attr_name = feed_entry.title
        self._attr_distance = feed_entry.distance_to_home
        self._attr_latitude = feed_entry.coordinates[0]
        self._attr_longitude = feed_entry.coordinates[1]
        self._attr_attribution = feed_entry.attribution
        self._place = feed_entry.place
        self._magnitude = feed_entry.magnitude
        self._time = feed_entry.time
        self._updated = feed_entry.updated
        self._status = feed_entry.status
        self._type = feed_entry.type
        self._alert = feed_entry.alert

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        return {
            key: value
            for key, value in (
                (ATTR_EXTERNAL_ID, self._external_id),
                (ATTR_PLACE, self._place),
                (ATTR_MAGNITUDE, self._magnitude),
                (ATTR_TIME, self._time),
                (ATTR_UPDATED, self._updated),
                (ATTR_STATUS, self._status),
                (ATTR_TYPE, self._type),
                (ATTR_ALERT, self._alert),
            )
            if value or isinstance(value, bool)
        }
