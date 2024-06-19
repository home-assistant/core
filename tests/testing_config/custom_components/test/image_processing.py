"""Provide a mock image processing."""

from homeassistant.components.image_processing import ImageProcessingEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities_callback: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the test image_processing platform."""
    async_add_entities_callback([TestImageProcessing("camera.demo_camera", "Test")])


class TestImageProcessing(ImageProcessingEntity):
    """Test image processing entity."""

    def __init__(self, camera_entity, name) -> None:
        """Initialize test image processing."""
        self._name = name
        self._camera = camera_entity
        self._count = 0
        self._image = ""

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state."""
        return False

    @property
    def camera_entity(self):
        """Return camera entity id from process pictures."""
        return self._camera

    @property
    def name(self):
        """Return the name of the entity."""
        return self._name

    @property
    def state(self):
        """Return the state of the entity."""
        return self._count

    @property
    def extra_state_attributes(self):
        """Return device specific state attributes."""
        return {"image": self._image}

    def process_image(self, image):
        """Process image."""
        self._image = image
        self._count += 1
