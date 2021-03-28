"""Support for IGN Sismologia (Earthquakes) Feeds."""
from __future__ import annotations

from datetime import timedelta
import logging

from georss_ign_sismologia_client import IgnSismologiaFeedManager
import voluptuous as vol

from homeassistant.components.geo_location import PLATFORM_SCHEMA, GeolocationEvent
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_RADIUS,
    CONF_SCAN_INTERVAL,
    EVENT_HOMEASSISTANT_START,
    LENGTH_KILOMETERS,
)
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.dispatcher import async_dispatcher_connect, dispatcher_send
from homeassistant.helpers.event import track_time_interval

_LOGGER = logging.getLogger(__name__)

ATTR_EXTERNAL_ID = "external_id"
ATTR_IMAGE_URL = "image_url"
ATTR_MAGNITUDE = "magnitude"
ATTR_PUBLICATION_DATE = "publication_date"
ATTR_REGION = "region"
ATTR_TITLE = "title"

CONF_MINIMUM_MAGNITUDE = "minimum_magnitude"

DEFAULT_MINIMUM_MAGNITUDE = 0.0
DEFAULT_RADIUS_IN_KM = 50.0

SCAN_INTERVAL = timedelta(minutes=5)

SOURCE = "ign_sismologia"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS_IN_KM): vol.Coerce(float),
        vol.Optional(
            CONF_MINIMUM_MAGNITUDE, default=DEFAULT_MINIMUM_MAGNITUDE
        ): cv.positive_float,
    }
)


def setup_platform(hass, config, add_entities, discovery_info=None):
    """Set up the IGN Sismologia Feed platform."""
    scan_interval = config.get(CONF_SCAN_INTERVAL, SCAN_INTERVAL)
    coordinates = (
        config.get(CONF_LATITUDE, hass.config.latitude),
        config.get(CONF_LONGITUDE, hass.config.longitude),
    )
    radius_in_km = config[CONF_RADIUS]
    minimum_magnitude = config[CONF_MINIMUM_MAGNITUDE]
    # Initialize the entity manager.
    feed = IgnSismologiaFeedEntityManager(
        hass, add_entities, scan_interval, coordinates, radius_in_km, minimum_magnitude
    )

    def start_feed_manager(event):
        """Start feed manager."""
        feed.startup()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_START, start_feed_manager)


class IgnSismologiaFeedEntityManager:
    """Feed Entity Manager for IGN Sismologia GeoRSS feed."""

    def __init__(
        self,
        hass,
        add_entities,
        scan_interval,
        coordinates,
        radius_in_km,
        minimum_magnitude,
    ):
        """Initialize the Feed Entity Manager."""

        self._hass = hass
        self._feed_manager = IgnSismologiaFeedManager(
            self._generate_entity,
            self._update_entity,
            self._remove_entity,
            coordinates,
            filter_radius=radius_in_km,
            filter_minimum_magnitude=minimum_magnitude,
        )
        self._add_entities = add_entities
        self._scan_interval = scan_interval

    def startup(self):
        """Start up this manager."""
        self._feed_manager.update()
        self._init_regular_updates()

    def _init_regular_updates(self):
        """Schedule regular updates at the specified interval."""
        track_time_interval(
            self._hass, lambda now: self._feed_manager.update(), self._scan_interval
        )

    def get_entry(self, external_id):
        """Get feed entry by external id."""
        return self._feed_manager.feed_entries.get(external_id)

    def _generate_entity(self, external_id):
        """Generate new entity."""
        new_entity = IgnSismologiaLocationEvent(self, external_id)
        # Add new entities to HA.
        self._add_entities([new_entity], True)

    def _update_entity(self, external_id):
        """Update entity."""
        dispatcher_send(self._hass, f"ign_sismologia_update_{external_id}")

    def _remove_entity(self, external_id):
        """Remove entity."""
        dispatcher_send(self._hass, f"ign_sismologia_delete_{external_id}")


class IgnSismologiaLocationEvent(GeolocationEvent):
    """This represents an external event with IGN Sismologia feed data."""

    def __init__(self, feed_manager, external_id):
        """Initialize entity with data from feed entry."""
        self._feed_manager = feed_manager
        self._external_id = external_id
        self._title = None
        self._distance = None
        self._latitude = None
        self._longitude = None
        self._attribution = None
        self._region = None
        self._magnitude = None
        self._publication_date = None
        self._image_url = None
        self._remove_signal_delete = None
        self._remove_signal_update = None

    async def async_added_to_hass(self):
        """Call when entity is added to hass."""
        self._remove_signal_delete = async_dispatcher_connect(
            self.hass,
            f"ign_sismologia_delete_{self._external_id}",
            self._delete_callback,
        )
        self._remove_signal_update = async_dispatcher_connect(
            self.hass,
            f"ign_sismologia_update_{self._external_id}",
            self._update_callback,
        )

    @callback
    def _delete_callback(self):
        """Remove this entity."""
        self._remove_signal_delete()
        self._remove_signal_update()
        self.hass.async_create_task(self.async_remove(force_remove=True))

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    @property
    def should_poll(self):
        """No polling needed for IGN Sismologia feed location events."""
        return False

    async def async_update(self):
        """Update this entity from the data held in the feed manager."""
        _LOGGER.debug("Updating %s", self._external_id)
        feed_entry = self._feed_manager.get_entry(self._external_id)
        if feed_entry:
            self._update_from_feed(feed_entry)

    def _update_from_feed(self, feed_entry):
        """Update the internal state from the provided feed entry."""
        self._title = feed_entry.title
        self._distance = feed_entry.distance_to_home
        self._latitude = feed_entry.coordinates[0]
        self._longitude = feed_entry.coordinates[1]
        self._attribution = feed_entry.attribution
        self._region = feed_entry.region
        self._magnitude = feed_entry.magnitude
        self._publication_date = feed_entry.published
        self._image_url = feed_entry.image_url

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:pulse"

    @property
    def source(self) -> str:
        """Return source value of this external event."""
        return SOURCE

    @property
    def name(self) -> str | None:
        """Return the name of the entity."""
        if self._magnitude and self._region:
            return f"M {self._magnitude:.1f} - {self._region}"
        if self._magnitude:
            return f"M {self._magnitude:.1f}"
        if self._region:
            return self._region
        return self._title

    @property
    def distance(self) -> float | None:
        """Return distance value of this external event."""
        return self._distance

    @property
    def latitude(self) -> float | None:
        """Return latitude value of this external event."""
        return self._latitude

    @property
    def longitude(self) -> float | None:
        """Return longitude value of this external event."""
        return self._longitude

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return LENGTH_KILOMETERS

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        attributes = {}
        for key, value in (
            (ATTR_EXTERNAL_ID, self._external_id),
            (ATTR_TITLE, self._title),
            (ATTR_REGION, self._region),
            (ATTR_MAGNITUDE, self._magnitude),
            (ATTR_ATTRIBUTION, self._attribution),
            (ATTR_PUBLICATION_DATE, self._publication_date),
            (ATTR_IMAGE_URL, self._image_url),
        ):
            if value or isinstance(value, bool):
                attributes[key] = value
        return attributes
