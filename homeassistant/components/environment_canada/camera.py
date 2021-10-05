"""Support for the Environment Canada radar imagery."""
from __future__ import annotations

import datetime

from homeassistant.components.camera import Camera
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.util import Throttle

from .const import DOMAIN

ATTR_UPDATED = "updated"

CONF_ATTRIBUTION = "Data provided by Environment Canada"
CONF_STATION = "station"
CONF_LOOP = "loop"
CONF_PRECIP_TYPE = "precip_type"

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=10)


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Add a weather entity from a config_entry."""
    coordinator = hass.data[DOMAIN][config_entry.entry_id]["radar_coordinator"]
    async_add_entities(
        [
            ECCamera(coordinator, config_entry.data[CONF_NAME], True),
        ]
    )


class ECCamera(Camera):
    """Implementation of an Environment Canada radar camera."""

    def __init__(self, radar_object, camera_name, is_loop):
        """Initialize the camera."""
        super().__init__()

        self.radar_object = radar_object
        self.camera_name = camera_name
        self.is_loop = is_loop
        self.content_type = "image/gif"
        self.image = None
        self.timestamp = None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        await self.async_update()
        return self.image

    @property
    def name(self):
        """Return the name of the camera."""
        if self.camera_name is not None:
            return self.camera_name
        return "Environment Canada Radar"

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return {ATTR_ATTRIBUTION: CONF_ATTRIBUTION, ATTR_UPDATED: self.timestamp}

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Update radar image."""
        self.image = await self.hass.async_add_executor_job(self.radar_object.get_loop)
        self.timestamp = self.radar_object.timestamp
