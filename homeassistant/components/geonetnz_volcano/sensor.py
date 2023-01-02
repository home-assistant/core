"""Feed Entity Manager Sensor support for GeoNet NZ Volcano Feeds."""
from __future__ import annotations

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_LATITUDE, ATTR_LONGITUDE, UnitOfLength
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt
from homeassistant.util.unit_conversion import DistanceConverter

from .const import (
    ATTR_ACTIVITY,
    ATTR_DISTANCE,
    ATTR_EXTERNAL_ID,
    ATTR_HAZARDS,
    DEFAULT_ICON,
    DOMAIN,
    FEED,
    IMPERIAL_UNITS,
)

_LOGGER = logging.getLogger(__name__)

ATTR_LAST_UPDATE = "feed_last_update"
ATTR_LAST_UPDATE_SUCCESSFUL = "feed_last_update_successful"


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the GeoNet NZ Volcano Feed platform."""
    manager = hass.data[DOMAIN][FEED][entry.entry_id]

    @callback
    def async_add_sensor(feed_manager, external_id, unit_system):
        """Add sensor entity from feed."""
        new_entity = GeonetnzVolcanoSensor(
            entry.entry_id, feed_manager, external_id, unit_system
        )
        _LOGGER.debug("Adding sensor %s", new_entity)
        async_add_entities([new_entity], True)

    manager.listeners.append(
        async_dispatcher_connect(
            hass, manager.async_event_new_entity(), async_add_sensor
        )
    )
    hass.async_create_task(manager.async_update())
    _LOGGER.debug("Sensor setup done")


class GeonetnzVolcanoSensor(SensorEntity):
    """This represents an external event with GeoNet NZ Volcano feed data."""

    _attr_should_poll = False

    def __init__(self, config_entry_id, feed_manager, external_id, unit_system):
        """Initialize entity with data from feed entry."""
        self._config_entry_id = config_entry_id
        self._feed_manager = feed_manager
        self._external_id = external_id
        self._unit_system = unit_system
        self._title = None
        self._distance = None
        self._latitude = None
        self._longitude = None
        self._attribution = None
        self._alert_level = None
        self._activity = None
        self._hazards = None
        self._feed_last_update = None
        self._feed_last_update_successful = None
        self._remove_signal_update = None

    async def async_added_to_hass(self) -> None:
        """Call when entity is added to hass."""
        self._remove_signal_update = async_dispatcher_connect(
            self.hass,
            f"geonetnz_volcano_update_{self._external_id}",
            self._update_callback,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Call when entity will be removed from hass."""
        if self._remove_signal_update:
            self._remove_signal_update()

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    async def async_update(self) -> None:
        """Update this entity from the data held in the feed manager."""
        _LOGGER.debug("Updating %s", self._external_id)
        feed_entry = self._feed_manager.get_entry(self._external_id)
        last_update = self._feed_manager.last_update()
        last_update_successful = self._feed_manager.last_update_successful()
        if feed_entry:
            self._update_from_feed(feed_entry, last_update, last_update_successful)

    def _update_from_feed(self, feed_entry, last_update, last_update_successful):
        """Update the internal state from the provided feed entry."""
        self._title = feed_entry.title
        # Convert distance if not metric system.
        if self._unit_system == IMPERIAL_UNITS:
            self._distance = round(
                DistanceConverter.convert(
                    feed_entry.distance_to_home,
                    UnitOfLength.KILOMETERS,
                    UnitOfLength.MILES,
                ),
                1,
            )
        else:
            self._distance = round(feed_entry.distance_to_home, 1)
        self._latitude = round(feed_entry.coordinates[0], 5)
        self._longitude = round(feed_entry.coordinates[1], 5)
        self._attr_attribution = feed_entry.attribution
        self._alert_level = feed_entry.alert_level
        self._activity = feed_entry.activity
        self._hazards = feed_entry.hazards
        self._feed_last_update = dt.as_utc(last_update) if last_update else None
        self._feed_last_update_successful = (
            dt.as_utc(last_update_successful) if last_update_successful else None
        )

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._alert_level

    @property
    def icon(self):
        """Return the icon to use in the frontend, if any."""
        return DEFAULT_ICON

    @property
    def name(self) -> str | None:
        """Return the name of the entity."""
        return f"Volcano {self._title}"

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        return "alert level"

    @property
    def extra_state_attributes(self):
        """Return the device state attributes."""
        attributes = {}
        for key, value in (
            (ATTR_EXTERNAL_ID, self._external_id),
            (ATTR_ACTIVITY, self._activity),
            (ATTR_HAZARDS, self._hazards),
            (ATTR_LONGITUDE, self._longitude),
            (ATTR_LATITUDE, self._latitude),
            (ATTR_DISTANCE, self._distance),
            (ATTR_LAST_UPDATE, self._feed_last_update),
            (ATTR_LAST_UPDATE_SUCCESSFUL, self._feed_last_update_successful),
        ):
            if value or isinstance(value, bool):
                attributes[key] = value
        return attributes
