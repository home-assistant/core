"""Support for the Environment Canada radar imagery."""
from __future__ import annotations

from homeassistant.components.camera import Camera
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import ATTR_OBSERVATION_TIME, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
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
        if not hasattr(self.radar_object, "timestamp"):
            return None
        self.observation_time = self.radar_object.timestamp
        return self.radar_object.image

    @property
    def extra_state_attributes(self):
        """Return the state attributes of the device."""
        return {ATTR_OBSERVATION_TIME: self.observation_time}
