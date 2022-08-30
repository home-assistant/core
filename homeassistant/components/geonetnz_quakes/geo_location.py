"""Geolocation support for GeoNet NZ Quakes Feeds."""
from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any

from aio_geojson_geonetnz_quakes.feed_entry import GeonetnzQuakesFeedEntry

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_TIME,
    CONF_UNIT_SYSTEM_IMPERIAL,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_system import IMPERIAL_SYSTEM

from . import GeonetnzQuakesFeedEntityManager
from .const import DOMAIN, FEED

_LOGGER = logging.getLogger(__name__)

ATTR_DEPTH = "depth"
ATTR_EXTERNAL_ID = "external_id"
ATTR_LOCALITY = "locality"
ATTR_MAGNITUDE = "magnitude"
ATTR_MMI = "mmi"
ATTR_PUBLICATION_DATE = "publication_date"
ATTR_QUALITY = "quality"

# An update of this entity is not making a web request, but uses internal data only.
PARALLEL_UPDATES = 0

SOURCE = "geonetnz_quakes"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the GeoNet NZ Quakes Feed platform."""
    manager: GeonetnzQuakesFeedEntityManager = hass.data[DOMAIN][FEED][entry.entry_id]

    @callback
    def async_add_geolocation(
        feed_manager: GeonetnzQuakesFeedEntityManager,
        integration_id: str,
        external_id: str,
    ) -> None:
        """Add geolocation entity from feed."""
        new_entity = GeonetnzQuakesEvent(feed_manager, integration_id, external_id)
        _LOGGER.debug("Adding geolocation %s", new_entity)
        async_add_entities([new_entity], True)

    manager.listeners.append(
        async_dispatcher_connect(
            hass, manager.async_event_new_entity(), async_add_geolocation
        )
    )
    # Do not wait for update here so that the setup can be completed and because an
    # update will fetch data from the feed via HTTP and then process that data.
    hass.async_create_task(manager.async_update())
    _LOGGER.debug("Geolocation setup done")


class GeonetnzQuakesEvent(GeolocationEvent):
    """This represents an external event with GeoNet NZ Quakes feed data."""

    _attr_icon = "mdi:pulse"
    _attr_should_poll = False
    _attr_source = SOURCE

    def __init__(
        self,
        feed_manager: GeonetnzQuakesFeedEntityManager,
        integration_id: str,
        external_id: str,
    ) -> None:
        """Initialize entity with data from feed entry."""
        self._feed_manager = feed_manager
        self._external_id = external_id
        self._attr_unique_id = f"{integration_id}_{external_id}"
        self._attr_unit_of_measurement = LENGTH_KILOMETERS
        self._depth = None
        self._locality = None
        self._magnitude = None
        self._mmi = None
        self._quality = None
        self._time = None
        self._remove_signal_delete: Callable[[], None]
        self._remove_signal_update: Callable[[], None]

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        if self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
            self._attr_unit_of_measurement = LENGTH_MILES
        self._remove_signal_delete = async_dispatcher_connect(
            self.hass,
            f"geonetnz_quakes_delete_{self._external_id}",
            self._delete_callback,
        )
        self._remove_signal_update = async_dispatcher_connect(
            self.hass,
            f"geonetnz_quakes_update_{self._external_id}",
            self._update_callback,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed from hass."""
        self._remove_signal_delete()
        self._remove_signal_update()
        # Remove from entity registry.
        entity_registry = er.async_get(self.hass)
        if self.entity_id in entity_registry.entities:
            entity_registry.async_remove(self.entity_id)

    @callback
    def _delete_callback(self) -> None:
        """Remove this entity."""
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

    def _update_from_feed(self, feed_entry: GeonetnzQuakesFeedEntry) -> None:
        """Update the internal state from the provided feed entry."""
        self._attr_name = feed_entry.title
        # Convert distance if not metric system.
        if self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
            self._attr_distance = IMPERIAL_SYSTEM.length(
                feed_entry.distance_to_home, LENGTH_KILOMETERS
            )
        else:
            self._attr_distance = feed_entry.distance_to_home
        self._attr_latitude = feed_entry.coordinates[0]
        self._attr_longitude = feed_entry.coordinates[1]
        self._attr_attribution = feed_entry.attribution
        self._depth = feed_entry.depth
        self._locality = feed_entry.locality
        self._magnitude = feed_entry.magnitude
        self._mmi = feed_entry.mmi
        self._quality = feed_entry.quality
        self._time = feed_entry.time

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        attributes = {}
        for key, value in (
            (ATTR_EXTERNAL_ID, self._external_id),
            (ATTR_DEPTH, self._depth),
            (ATTR_LOCALITY, self._locality),
            (ATTR_MAGNITUDE, self._magnitude),
            (ATTR_MMI, self._mmi),
            (ATTR_QUALITY, self._quality),
            (ATTR_TIME, self._time),
        ):
            if value or isinstance(value, bool):
                attributes[key] = value
        return attributes
