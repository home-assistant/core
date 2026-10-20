"""Tests for the Image classification integration."""

from io import BytesIO
from pathlib import Path
from typing import Any, override

from PIL import Image, ImageDraw
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components import ai_task
from homeassistant.components.camera import Camera
from homeassistant.components.image_classification.const import (
    CONF_AI_TASK_ENTITY_ID,
    CONF_BOTTOM,
    CONF_LEFT,
    CONF_RIGHT,
    CONF_TOP,
    DOMAIN,
)
from homeassistant.const import CONF_DEVICE_CLASS, CONF_ENTITY_ID, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.device_registry import DeviceInfo

CAMERA = "camera.garage_camera"
CLASSIFIER = "ai_task.classifier"
ENTITY_ID = "binary_sensor.garage_camera_garage"
REGION = {CONF_LEFT: 25, CONF_TOP: 20, CONF_RIGHT: 75, CONF_BOTTOM: 90}
TEST_DOMAIN = "test"
USER_INPUT = {
    CONF_ENTITY_ID: CAMERA,
    CONF_DEVICE_CLASS: "occupancy",
    CONF_NAME: "Garage",
    CONF_AI_TASK_ENTITY_ID: CLASSIFIER,
}
CONFIDENT_ON = {"on": 0.9, "off": 0.1}
CONFIDENT_OFF = {"on": 0.2, "off": 0.8}


def render_frame(
    *, car: bool, size: tuple[int, int] = (320, 180), image_format: str = "JPEG"
) -> bytes:
    """Render a garage frame, with or without a car on the spot."""
    image = Image.new("RGB", (320, 180), (150, 140, 120))
    draw = ImageDraw.Draw(image)
    for y in range(20, 120, 20):
        draw.line((60, y, 260, y), fill=(110, 105, 95), width=2)
    if car:
        draw.rounded_rectangle((100, 50, 220, 150), 18, fill=(40, 40, 70))
        draw.rectangle((120, 60, 200, 90), fill=(180, 200, 220))
    buffer = BytesIO()
    image.resize(size).save(buffer, image_format)
    return buffer.getvalue()


class FakeCamera(Camera):
    """A camera whose next frame the test sets."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self) -> None:
        """Initialize the camera."""
        super().__init__()
        self._attr_unique_id = "garage"
        self._attr_device_info = DeviceInfo(
            identifiers={(TEST_DOMAIN, "garage")}, name="Garage camera"
        )
        self.frame: bytes | None = render_frame(car=True)

    @override
    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the current frame; None means the camera has no image."""
        return self.frame


class FakeClassifier(ai_task.AITaskEntity):
    """An AI Task entity whose next answer the test sets."""

    _attr_name = "Classifier"
    _attr_supported_features = ai_task.AITaskEntityFeature.CLASSIFY_IMAGE

    def __init__(self) -> None:
        """Initialize the classifier."""
        super().__init__()
        self.probabilities = CONFIDENT_ON
        self.error: Exception | None = None
        self.tasks: list[ai_task.ClassifyImageTask] = []
        self.images: list[bytes] = []

    @override
    async def _async_classify_image(
        self, task: ai_task.ClassifyImageTask
    ) -> ai_task.ChoiceAnswer:
        """Record the task and return the set answer."""
        self.tasks.append(task)
        # The camera frame is a temporary file, removed after the task.
        self.images.append(
            await self.hass.async_add_executor_job(task.image.path.read_bytes)
        )
        if self.error is not None:
            raise self.error
        return ai_task.ChoiceAnswer(
            choice=max(self.probabilities, key=self.probabilities.__getitem__),
            probabilities=dict(self.probabilities),
        )


async def setup_integration(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Set up the integration."""
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()


async def teach(hass: HomeAssistant, entry: MockConfigEntry, state: str) -> FlowResult:
    """Teach the current camera frame through the options flow."""
    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "teach"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"state": state}
    )
    await hass.async_block_till_done()
    return result


async def teach_both(
    hass: HomeAssistant, entry: MockConfigEntry, camera: FakeCamera
) -> None:
    """Teach a car frame as on and an empty frame as off."""
    camera.frame = render_frame(car=True)
    await teach(hass, entry, "on")
    camera.frame = render_frame(car=False)
    await teach(hass, entry, "off")


def stored_frames(
    hass_storage: dict[str, Any], entry: MockConfigEntry
) -> list[dict[str, Any]]:
    """Return the stored index of taught frames."""
    return hass_storage[f"{DOMAIN}.{entry.entry_id}"]["data"]["frames"]


def frame_files(config_dir: Path, entry: MockConfigEntry) -> set[str]:
    """Return the ids of the frame files on disk."""
    return {path.stem for path in (config_dir / DOMAIN / entry.entry_id).glob("*.jpg")}
