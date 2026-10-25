"""Provides camera entities for Home Connect."""

import asyncio
from typing import override

from aiohomeconnect.model.error import HomeConnectError

from homeassistant.components.camera import Camera, CameraEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .common import setup_home_connect_entry
from .const import DOMAIN
from .coordinator import HomeConnectApplianceCoordinator, HomeConnectConfigEntry
from .entity import HomeConnectEntity
from .utils import RE_CAMEL_CASE, get_dict_from_home_connect_error

PARALLEL_UPDATES = 0

CAMERAS = (
    CameraEntityDescription(
        key="Refrigeration.FridgeFreezer.Status.DoorCameraPresentRefrigerator",
        translation_key="refrigerator_door_camera",
    ),
    CameraEntityDescription(
        key="Refrigeration.FridgeFreezer.Status.InteriorCameraPresentRefrigerator",
        translation_key="refrigerator_interior_camera",
    ),
)

CAMERAS_BY_KEY = {description.key: description for description in CAMERAS}


def _get_description_for_camera(camera_key: str) -> CameraEntityDescription:
    """Get the entity description for a camera, naming unknown ones after their key."""
    if description := CAMERAS_BY_KEY.get(camera_key):
        return description
    return CameraEntityDescription(
        key=camera_key,
        translation_key="camera",
        translation_placeholders={
            "camera": RE_CAMEL_CASE.sub(" ", camera_key.rsplit(".", 1)[-1]).capitalize()
        },
    )


def _get_entities_for_appliance(
    appliance_coordinator: HomeConnectApplianceCoordinator,
) -> list[HomeConnectEntity]:
    """Get a list of entities."""
    return [
        HomeConnectCameraEntity(
            appliance_coordinator, _get_description_for_camera(camera_key)
        )
        for camera_key in appliance_coordinator.data.images
    ]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: HomeConnectConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Home Connect camera entities."""
    setup_home_connect_entry(
        hass,
        entry,
        _get_entities_for_appliance,
        async_add_entities,
    )


class HomeConnectCameraEntity(HomeConnectEntity, Camera):
    """Camera entity showing the latest image taken by an appliance camera."""

    _image_key: str | None = None
    _image: bytes | None = None

    def __init__(
        self,
        appliance_coordinator: HomeConnectApplianceCoordinator,
        desc: CameraEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(appliance_coordinator, desc, context_override=desc.key)
        Camera.__init__(self)
        self._image_lock = asyncio.Lock()

    @property
    @override
    def available(self) -> bool:
        """Return True if the camera has taken an image."""
        return super().available and self.bsh_key in self.appliance.images

    @override
    def update_native_value(self) -> None:
        """Point the entity to the latest image taken by the camera."""
        image = self.appliance.images.get(self.bsh_key)
        if image is None or image.image_key == self._image_key:
            return
        self._image_key = image.image_key
        self._image = None

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return bytes of the latest image taken by the camera."""
        # Serialize the requests so that concurrent ones share a single download
        async with self._image_lock:
            if self._image is not None or (image_key := self._image_key) is None:
                return self._image
            try:
                image = await self.coordinator.client.get_image(
                    self.appliance.info.ha_id, image_key=image_key
                )
            except HomeConnectError as error:
                raise HomeAssistantError(
                    translation_domain=DOMAIN,
                    translation_key="fetch_image_error",
                    translation_placeholders={
                        **get_dict_from_home_connect_error(error),
                        "entity_id": self.entity_id,
                    },
                ) from error
            if image_key == self._image_key:
                # Only cache the image if no newer one was taken while downloading
                self._image = image
            return image
