"""Support for the Environment Canada radar imagery."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import trigger_import
from .const import ATTR_OBSERVATION_TIME, CONF_STATION, DOMAIN

CONF_LOOP = "loop"
CONF_PRECIP_TYPE = "precip_type"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_LOOP, default=True): cv.boolean,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_STATION): cv.matches_regex(r"^C[A-Z]{4}$|^[A-Z]{3}$"),
        vol.Inclusive(CONF_LATITUDE, "latlon"): cv.latitude,
        vol.Inclusive(CONF_LONGITUDE, "latlon"): cv.longitude,
        vol.Optional(CONF_PRECIP_TYPE): vol.In(["RAIN", "SNOW"]),
    }
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
    async_add_entities([ECCamera(coordinator)])


class ECCamera(CoordinatorEntity, Camera):
    """Implementation of an Environment Canada radar camera."""

    def __init__(self, coordinator):
        """Initialize the camera."""
        super().__init__(coordinator)
        Camera.__init__(self)

        self.radar_object = coordinator.ec_data
        self._attr_name = f"{coordinator.config_entry.title} Radar"
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}-radar"
        self._attr_attribution = self.radar_object.metadata["attribution"]
        self._attr_entity_registry_enabled_default = False

        self.content_type = "image/gif"
        self.image = None
        self.observation_time = None

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        self.observation_time = self.radar_object.timestamp
        return self.radar_object.image

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return {ATTR_OBSERVATION_TIME: self.observation_time}
