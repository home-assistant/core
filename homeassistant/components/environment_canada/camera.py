"""Support for the Environment Canada radar imagery."""
from __future__ import annotations

import datetime

import voluptuous as vol

from homeassistant.components.camera import Camera
from homeassistant.const import ATTR_ATTRIBUTION, CONF_NAME
from homeassistant.helpers import entity_platform

from . import ECBaseEntity
from .const import ATTR_OBSERVATION_TIME, DEFAULT_NAME, DOMAIN

ATTR_UPDATED = "updated"

CONF_LOOP = "loop"
CONF_PRECIP_TYPE = "precip_type"
CONF_RADAR_TYPE = "radar_type"

MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(minutes=5)
SERVICE_SET_RADAR_TYPE = "set_radar_type"

SET_RADAR_TYPE_SCHEMA = {
    vol.Required(CONF_RADAR_TYPE, default="Auto"): vol.In(["Auto", "Rain", "Snow"])
}


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up the Environment Canada camera."""

    coordinator = hass.data[DOMAIN][config_entry.entry_id]["radar_coordinator"]

    async_add_entities([ECCamera(coordinator, config_entry.data)], True)

    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_RADAR_TYPE, SET_RADAR_TYPE_SCHEMA, "async_set_radar_type"
    )


class ECCamera(ECBaseEntity, Camera):
    """Implementation of an Environment Canada radar camera."""

    def __init__(self, coordinator, config):
        """Initialize the EC camera."""
        name = f"{config.get(CONF_NAME, DEFAULT_NAME)} Radar"
        ECBaseEntity.__init__(self, coordinator, config, name)
        Camera.__init__(self)

        self.content_type = "image/gif"
        self.image = None
        self.timestamp = None
        self._unique_id_tail = "radar"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        self.timestamp = self._coordinator.data.timestamp
        return self._coordinator.data.image

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return {
            ATTR_ATTRIBUTION: self.attribution,
            ATTR_OBSERVATION_TIME: self.timestamp,
        }

    async def async_set_radar_type(self, radar_type):
        """Set the type of radar to display."""
        self._coordinator.ec_data.precip_type = radar_type.lower()
        await self._coordinator.async_config_entry_first_refresh()

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:radar"
