"""Generic GeoRSS events service.

Retrieves current events (typically incidents or alerts) in GeoRSS format, and
shows information on events filtered by distance to the HA instance's location
and grouped by category.
"""

from __future__ import annotations

from datetime import timedelta
import logging

from georss_client import UPDATE_OK, UPDATE_OK_NO_DATA
from georss_generic_client import GenericFeed
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA as SENSOR_PLATFORM_SCHEMA,
    SensorEntity,
)
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
    CONF_RADIUS,
    CONF_UNIT_OF_MEASUREMENT,
    CONF_URL,
    UnitOfLength,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

ATTR_CATEGORY = "category"
ATTR_DISTANCE = "distance"
ATTR_TITLE = "title"

CONF_CATEGORIES = "categories"

DEFAULT_NAME = "Event Service"
DEFAULT_RADIUS_IN_KM = 20.0
DEFAULT_UNIT_OF_MEASUREMENT = "Events"

DOMAIN = "geo_rss_events"

SCAN_INTERVAL = timedelta(minutes=5)

PLATFORM_SCHEMA = SENSOR_PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_URL): cv.string,
        vol.Optional(CONF_LATITUDE): cv.latitude,
        vol.Optional(CONF_LONGITUDE): cv.longitude,
        vol.Optional(CONF_RADIUS, default=DEFAULT_RADIUS_IN_KM): vol.Coerce(float),
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_CATEGORIES, default=[]): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(
            CONF_UNIT_OF_MEASUREMENT, default=DEFAULT_UNIT_OF_MEASUREMENT
        ): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the GeoRSS component."""
    latitude = config.get(CONF_LATITUDE, hass.config.latitude)
    longitude = config.get(CONF_LONGITUDE, hass.config.longitude)
    url = config.get(CONF_URL)
    radius_in_km = config.get(CONF_RADIUS)
    name = config.get(CONF_NAME)
    categories = config.get(CONF_CATEGORIES)
    unit_of_measurement = config.get(CONF_UNIT_OF_MEASUREMENT)

    _LOGGER.debug(
        "latitude=%s, longitude=%s, url=%s, radius=%s",
        latitude,
        longitude,
        url,
        radius_in_km,
    )

    # Create all sensors based on categories.
    devices = []
    if not categories:
        device = GeoRssServiceSensor(
            (latitude, longitude), url, radius_in_km, None, name, unit_of_measurement
        )
        devices.append(device)
    else:
        for category in categories:
            device = GeoRssServiceSensor(
                (latitude, longitude),
                url,
                radius_in_km,
                category,
                name,
                unit_of_measurement,
            )
            devices.append(device)
    add_entities(devices, True)


class GeoRssServiceSensor(SensorEntity):
    """Representation of a Sensor."""

    _attr_icon = "mdi:alert"

    def __init__(
        self, coordinates, url, radius, category, service_name, unit_of_measurement
    ):
        """Initialize the sensor."""
        self._attr_name = f"{service_name} {'Any' if category is None else category}"
        self._attr_native_unit_of_measurement = unit_of_measurement

        self._feed = GenericFeed(
            coordinates,
            url,
            filter_radius=radius,
            filter_categories=None if not category else [category],
        )

    def update(self) -> None:
        """Update this sensor from the GeoRSS service."""

        status, feed_entries = self._feed.update()
        if status == UPDATE_OK:
            _LOGGER.debug(
                "Adding events to sensor %s: %s", self.entity_id, feed_entries
            )
            self._attr_native_value = len(feed_entries)
            # And now compute the attributes from the filtered events.
            matrix = {}
            for entry in feed_entries:
                matrix[entry.title] = (
                    f"{entry.distance_to_home:.0f}{UnitOfLength.KILOMETERS}"
                )
            self._attr_extra_state_attributes = matrix
        elif status == UPDATE_OK_NO_DATA:
            _LOGGER.debug("Update successful, but no data received from %s", self._feed)
            # Don't change the state or state attributes.
        else:
            _LOGGER.warning(
                "Update not successful, no data received from %s", self._feed
            )
            # If no events were found due to an error then just set state to
            # zero.
            self._attr_native_value = 0
            self._attr_extra_state_attributes = {}
