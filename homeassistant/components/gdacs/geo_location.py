"""Geolocation support for GDACS Feed."""
import logging
from typing import Optional

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_UNIT_SYSTEM_IMPERIAL,
    LENGTH_KILOMETERS,
    LENGTH_MILES,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util.unit_system import IMPERIAL_SYSTEM

from .const import (
    DEFAULT_ICON,
    DOMAIN,
    FEED,
    SIGNAL_DELETE_ENTITY,
    SIGNAL_UPDATE_ENTITY,
)

_LOGGER = logging.getLogger(__name__)

ATTR_ALERT_LEVEL = "alert_level"
ATTR_COUNTRY = "country"
ATTR_DESCRIPTION = "description"
ATTR_DURATION_IN_WEEK = "duration_in_week"
ATTR_EVENT_TYPE = "event_type"
ATTR_EXTERNAL_ID = "external_id"
ATTR_FROM_DATE = "from_date"
ATTR_POPULATION = "population"
ATTR_SEVERITY = "severity"
ATTR_TO_DATE = "to_date"
ATTR_VULNERABILITY = "vulnerability"

ICONS = {
    "DR": "mdi:water-off",
    "EQ": "mdi:pulse",
    "FL": "mdi:home-flood",
    "TC": "mdi:weather-hurricane",
    "TS": "mdi:waves",
    "VO": "mdi:image-filter-hdr",
}

# An update of this entity is not making a web request, but uses internal data only.
PARALLEL_UPDATES = 0

SOURCE = "gdacs"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the GDACS Feed platform."""
    manager = hass.data[DOMAIN][FEED][entry.entry_id]

    @callback
    def async_add_geolocation(feed_manager, external_id):
        """Add gelocation entity from feed."""
        new_entity = GdacsEvent(feed_manager, external_id)
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


class GdacsEvent(GeolocationEvent):
    """This represents an external event with GDACS feed data."""

    def __init__(self, feed_manager, external_id):
        """Initialize entity with data from feed entry."""
        self._feed_manager = feed_manager
        self._external_id = external_id
        self._title = None
        self._distance = None
        self._latitude = None
        self._longitude = None
        self._attribution = None
        self._alert_level = None
        self._country = None
        self._description = None
        self._duration_in_week = None
        self._event_type_short = None
        self._event_type = None
        self._from_date = None
        self._to_date = None
        self._population = None
        self._severity = None
        self._vulnerability = None
        self._version = None
        self._remove_signal_delete = None
        self._remove_signal_update = None

    async def async_added_to_hass(self):
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

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed from hass."""
        self._remove_signal_delete()
        self._remove_signal_update()

    @callback
    def _delete_callback(self):
        """Remove this entity."""
        self.hass.async_create_task(self.async_remove())

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    @property
    def should_poll(self):
        """No polling needed for GDACS feed location events."""
        return False

    async def async_update(self):
        """Update this entity from the data held in the feed manager."""
        _LOGGER.debug("Updating %s", self._external_id)
        feed_entry = self._feed_manager.get_entry(self._external_id)
        if feed_entry:
            self._update_from_feed(feed_entry)

    def _update_from_feed(self, feed_entry):
        """Update the internal state from the provided feed entry."""
        event_name = feed_entry.event_name
        if not event_name:
            # Earthquakes usually don't have an event name.
            event_name = f"{feed_entry.country} ({feed_entry.event_id})"
        self._title = f"{feed_entry.event_type}: {event_name}"
        # Convert distance if not metric system.
        if self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
            self._distance = IMPERIAL_SYSTEM.length(
                feed_entry.distance_to_home, LENGTH_KILOMETERS
            )
        else:
            self._distance = feed_entry.distance_to_home
        self._latitude = feed_entry.coordinates[0]
        self._longitude = feed_entry.coordinates[1]
        self._attribution = feed_entry.attribution
        self._alert_level = feed_entry.alert_level
        self._country = feed_entry.country
        self._description = feed_entry.title
        self._duration_in_week = feed_entry.duration_in_week
        self._event_type_short = feed_entry.event_type_short
        self._event_type = feed_entry.event_type
        self._from_date = feed_entry.from_date
        self._to_date = feed_entry.to_date
        self._population = feed_entry.population
        self._severity = feed_entry.severity
        self._vulnerability = feed_entry.vulnerability
        # Round vulnerability value if presented as float.
        if isinstance(self._vulnerability, float):
            self._vulnerability = round(self._vulnerability, 1)
        self._version = feed_entry.version

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        if self._event_type_short and self._event_type_short in ICONS:
            return ICONS[self._event_type_short]
        return DEFAULT_ICON

    @property
    def source(self) -> str:
        """Return source value of this external event."""
        return SOURCE

    @property
    def name(self) -> Optional[str]:
        """Return the name of the entity."""
        return self._title

    @property
    def distance(self) -> Optional[float]:
        """Return distance value of this external event."""
        return self._distance

    @property
    def latitude(self) -> Optional[float]:
        """Return latitude value of this external event."""
        return self._latitude

    @property
    def longitude(self) -> Optional[float]:
        """Return longitude value of this external event."""
        return self._longitude

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        if self.hass.config.units.name == CONF_UNIT_SYSTEM_IMPERIAL:
            return LENGTH_MILES
        return LENGTH_KILOMETERS

    @property
    def device_state_attributes(self):
        """Return the device state attributes."""
        attributes = {}
        for key, value in (
            (ATTR_EXTERNAL_ID, self._external_id),
            (ATTR_DESCRIPTION, self._description),
            (ATTR_ATTRIBUTION, self._attribution),
            (ATTR_EVENT_TYPE, self._event_type),
            (ATTR_ALERT_LEVEL, self._alert_level),
            (ATTR_COUNTRY, self._country),
            (ATTR_DURATION_IN_WEEK, self._duration_in_week),
            (ATTR_FROM_DATE, self._from_date),
            (ATTR_TO_DATE, self._to_date),
            (ATTR_POPULATION, self._population),
            (ATTR_SEVERITY, self._severity),
            (ATTR_VULNERABILITY, self._vulnerability),
        ):
            if value or isinstance(value, bool):
                attributes[key] = value
        return attributes
