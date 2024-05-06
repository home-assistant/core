"""Geolocation support for GDACS Feed."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
import logging
from typing import Any

from aio_georss_gdacs.feed_entry import GdacsFeedEntry

from homeassistant.components.geo_location import GeolocationEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_conversion import DistanceConverter
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import GdacsFeedEntityManager
from .const import DEFAULT_ICON, DOMAIN, FEED

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


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the GDACS Feed platform."""
    manager: GdacsFeedEntityManager = hass.data[DOMAIN][FEED][entry.entry_id]

    @callback
    def async_add_geolocation(
        feed_manager: GdacsFeedEntityManager, integration_id: str, external_id: str
    ) -> None:
        """Add geolocation entity from feed."""
        new_entity = GdacsEvent(feed_manager, integration_id, external_id)
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
    """Represents an external event with GDACS feed data."""

    _attr_should_poll = False
    _attr_source = SOURCE

    def __init__(
        self,
        feed_manager: GdacsFeedEntityManager,
        integration_id: str,
        external_id: str,
    ) -> None:
        """Initialize entity with data from feed entry."""
        self._feed_manager = feed_manager
        self._external_id = external_id
        self._attr_unique_id = f"{integration_id}_{external_id}"
        self._attr_unit_of_measurement = UnitOfLength.KILOMETERS
        self._alert_level: str | None = None
        self._country: str | None = None
        self._description: str | None = None
        self._duration_in_week: int | None = None
        self._event_type_short: str | None = None
        self._event_type: str | None = None
        self._from_date: datetime | None = None
        self._to_date: datetime | None = None
        self._population: str | None = None
        self._severity: str | None = None
        self._vulnerability: str | float | None = None
        self._version: int | None = None
        self._remove_signal_delete: Callable[[], None]
        self._remove_signal_update: Callable[[], None]

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        if self.hass.config.units is US_CUSTOMARY_SYSTEM:
            self._attr_unit_of_measurement = UnitOfLength.MILES
        self._remove_signal_delete = async_dispatcher_connect(
            self.hass, f"gdacs_delete_{self._external_id}", self._delete_callback
        )
        self._remove_signal_update = async_dispatcher_connect(
            self.hass, f"gdacs_update_{self._external_id}", self._update_callback
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

    def _update_from_feed(self, feed_entry: GdacsFeedEntry) -> None:
        """Update the internal state from the provided feed entry."""
        if not (event_name := feed_entry.event_name):
            # Earthquakes usually don't have an event name.
            event_name = f"{feed_entry.country} ({feed_entry.event_id})"
        self._attr_name = f"{feed_entry.event_type}: {event_name}"
        # Convert distance if not metric system.
        if self.hass.config.units is US_CUSTOMARY_SYSTEM:
            self._attr_distance = DistanceConverter.convert(
                feed_entry.distance_to_home, UnitOfLength.KILOMETERS, UnitOfLength.MILES
            )
        else:
            self._attr_distance = feed_entry.distance_to_home
        self._attr_latitude = feed_entry.coordinates[0]
        self._attr_longitude = feed_entry.coordinates[1]
        self._attr_attribution = feed_entry.attribution
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
    def icon(self) -> str:
        """Return the icon to use in the frontend, if any."""
        if self._event_type_short and self._event_type_short in ICONS:
            return ICONS[self._event_type_short]
        return DEFAULT_ICON

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        attributes = {}
        for key, value in (
            (ATTR_EXTERNAL_ID, self._external_id),
            (ATTR_DESCRIPTION, self._description),
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
