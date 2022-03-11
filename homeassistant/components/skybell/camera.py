"""Camera support for the Skybell HD Doorbell."""
from __future__ import annotations

import voluptuous as vol

from homeassistant.components.camera import (
    PLATFORM_SCHEMA,
    Camera,
    CameraEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MONITORED_CONDITIONS
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SkybellEntity
from .const import DOMAIN, IMAGE_ACTIVITY, IMAGE_AVATAR
from .coordinator import SkybellDataUpdateCoordinator

# Deprecated in Home Assistant 2022.4
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_MONITORED_CONDITIONS, default=[IMAGE_AVATAR]): vol.All(
            cv.ensure_list, [vol.In([IMAGE_AVATAR, IMAGE_ACTIVITY])]
        ),
        vol.Optional("activity_name"): cv.string,
        vol.Optional("avatar_name"): cv.string,
    }
)

CAMERA_TYPES: tuple[CameraEntityDescription, ...] = (
    CameraEntityDescription(key="activity", name="Last Activity"),
    CameraEntityDescription(key="avatar", name="Camera"),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Skybell switch."""
    async_add_entities(
        SkybellCamera(coordinator, description)
        for description in CAMERA_TYPES
        for coordinator in hass.data[DOMAIN][entry.entry_id]
    )


class SkybellCamera(SkybellEntity, Camera):
    """A camera implementation for Skybell devices."""

    coordinator: SkybellDataUpdateCoordinator

    def __init__(
        self,
        coordinator: SkybellDataUpdateCoordinator,
        description: EntityDescription,
    ) -> None:
        """Initialize a camera for a Skybell device."""
        super().__init__(coordinator)
        Camera.__init__(self)
        self.entity_description = description
        self._attr_name = f"{coordinator.name} {description.name}"
        self._attr_unique_id = f"{coordinator.device.device_id}_{description.key}"

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Get the latest camera image."""
        return self.coordinator.device.images[self.entity_description.key]
