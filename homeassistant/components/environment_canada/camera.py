"""Support for the Environment Canada radar imagery."""

from __future__ import annotations

from env_canada import ECMap
import voluptuous as vol

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import (
    AddConfigEntryEntitiesCallback,
    async_get_current_platform,
)
from homeassistant.helpers.typing import VolDictType
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTR_OBSERVATION_TIME
from .coordinator import ECConfigEntry, ECDataUpdateCoordinator

SERVICE_SET_RADAR_TYPE = "set_radar_type"
SET_RADAR_TYPE_SCHEMA: VolDictType = {
    vol.Required("radar_type"): vol.In(["Auto", "Rain", "Snow", "Precip Type"]),
}

_RADAR_TYPE_TO_LAYER: dict[str, str] = {
    "Rain": "rain",
    "Snow": "snow",
    "Precip Type": "precip_type",
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ECConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add a weather entity from a config_entry."""
    coordinator = config_entry.runtime_data.radar_coordinator
    async_add_entities([ECCameraEntity(coordinator)])

    platform = async_get_current_platform()
    platform.async_register_entity_service(
        SERVICE_SET_RADAR_TYPE,
        SET_RADAR_TYPE_SCHEMA,
        "async_set_radar_type",
    )


class ECCameraEntity(CoordinatorEntity[ECDataUpdateCoordinator[ECMap]], Camera):
    """Implementation of an Environment Canada radar camera."""

    _attr_has_entity_name = True
    _attr_translation_key = "radar"

    def __init__(self, coordinator: ECDataUpdateCoordinator[ECMap]) -> None:
        """Initialize the camera."""
        super().__init__(coordinator)
        Camera.__init__(self)

        self.radar_object = coordinator.ec_data
        self._attr_unique_id = f"{coordinator.config_entry.unique_id}-radar"
        self._attr_attribution = self.radar_object.metadata["attribution"]
        self._attr_entity_registry_enabled_default = False
        self._attr_device_info = coordinator.device_info

        self.content_type = "image/gif"

    async def async_added_to_hass(self) -> None:
        """When entity is added to hass."""
        await super().async_added_to_hass()
        # Trigger coordinator refresh when entity is enabled
        # since radar coordinator skips initial refresh during setup
        if not self.coordinator.last_update_success:
            await self.coordinator.async_request_refresh()

    def camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of camera image."""
        self._attr_extra_state_attributes = {
            ATTR_OBSERVATION_TIME: self.radar_object.timestamp,
        }
        return self.radar_object.image

    async def async_set_radar_type(self, radar_type: str) -> None:
        """Set the type of radar to retrieve."""
        if radar_type == "Auto":
            # Choose rain for months April through October, snow otherwise
            layer = "rain" if dt_util.now().month in range(4, 11) else "snow"
        else:
            layer = _RADAR_TYPE_TO_LAYER[radar_type]

        # Apply new layer and clear cache to force refresh
        self.radar_object.layer = layer
        self.radar_object.clear_cache()
        await self.coordinator.async_request_refresh()
