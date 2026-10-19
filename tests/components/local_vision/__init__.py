"""Tests for the Local vision integration."""

from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.camera import Camera
from homeassistant.components.local_vision.const import (
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
ENTITY_ID = "binary_sensor.garage_camera_garage"
REGION = {CONF_LEFT: 25, CONF_TOP: 20, CONF_RIGHT: 75, CONF_BOTTOM: 90}
TEST_DOMAIN = "test"
USER_INPUT = {
    CONF_ENTITY_ID: CAMERA,
    CONF_DEVICE_CLASS: "occupancy",
    CONF_NAME: "Garage",
}


def render_frame(
    *,
    car: bool,
    shift: int = 0,
    brightness: float = 1.0,
    corner: bool = False,
    plain: bool = False,
) -> bytes:
    """Render a garage frame as JPEG, with or without a car on the spot.

    ``corner`` adds a box in the top left, outside the configured region.
    ``plain`` leaves out the door panels, so an empty spot shows nothing.
    """
    image = Image.new("RGB", (320, 180), (150, 140, 120))
    draw = ImageDraw.Draw(image)
    if not plain:
        for y in range(20, 120, 20):
            draw.line((60 + shift, y, 260 + shift, y), fill=(110, 105, 95), width=2)
    if car:
        draw.rounded_rectangle(
            (100 + shift, 50, 220 + shift, 150), 18, fill=(40, 40, 70)
        )
        draw.rectangle((120 + shift, 60, 200 + shift, 90), fill=(180, 200, 220))
    if corner:
        draw.rectangle((5, 5, 70, 30), fill=(20, 20, 20))
    image = image.point(lambda value: min(255, int(value * brightness)))
    buffer = BytesIO()
    image.save(buffer, "JPEG", quality=90)
    return buffer.getvalue()


def blank_frame() -> bytes:
    """Return a grey frame, as an offline camera might send."""
    buffer = BytesIO()
    Image.new("RGB", (320, 180), (128, 128, 128)).save(buffer, "JPEG")
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

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return the current frame; None means the camera has no image."""
        return self.frame


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
