"""Support for the Environment Canada radar imagery."""
from __future__ import annotations

import datetime

import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    CONF_NAME,
)
import homeassistant.helpers.config_validation as cv

from . import trigger_import
from .const import CONF_ATTRIBUTION, CONF_STATION, DOMAIN

CONF_LOOP = "loop"
CONF_PRECIP_TYPE = "precip_type"
ATTR_UPDATED = "updated"

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=10)

PLATFORM_SCHEMA = vol.All(
    cv.deprecated(CONF_LOOP),
    cv.deprecated(CONF_STATION),
    PLATFORM_SCHEMA=PLATFORM_SCHEMA.extend(
        {
            vol.Optional(CONF_NAME): cv.string,
            vol.Inclusive(CONF_LATITUDE, "latlon"): cv.latitude,
            vol.Inclusive(CONF_LONGITUDE, "latlon"): cv.longitude,
            vol.Optional(CONF_PRECIP_TYPE): vol.In(["RAIN", "SNOW"]),
        }
    ),
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the Environment Canada camera."""
    lat = config.get(CONF_LATITUDE, hass.config.latitude)
    lon = config.get(CONF_LONGITUDE, hass.config.longitude)

    config[CONF_LATITUDE] = lat
    config[CONF_LONGITUDE] = lon

    trigger_import(hass, config)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a weather entity from a config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["radar_coordinator"]

    async_add_entities(
        [
            ECCamera(
                coordinator.ec_data,
                f"{config_entry.title} Radar",
                f"{config_entry.unique_id}-radar",
            ),
        ]
    )


class ECCamera(Camera):
    """Implementation of an Environment Canada radar camera."""

    def __init__(self, radar_object, camera_name, unique_id):
        """Initialize the camera."""
        super().__init__()

        self.radar_object = radar_object
        self._attr_name = camera_name
        self._attr_unique_id = unique_id
        self.content_type = "image/gif"
        self.image = None
        self.timestamp = None

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        self.timestamp = self.radar_object.timestamp
        return self.radar_object.image

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return {ATTR_ATTRIBUTION: CONF_ATTRIBUTION, ATTR_UPDATED: self.timestamp}
