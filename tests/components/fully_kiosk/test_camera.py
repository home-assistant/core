"""Test the Fully Kiosk Browser camera platform."""

from unittest.mock import MagicMock

from homeassistant.components.camera import async_get_image
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_camera(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test the camera entity."""
    entity_camera = "camera.amazon_fire_camera"
    entity = hass.states.get(entity_camera)
    assert entity
    assert entity.state == "idle"
    entry = entity_registry.async_get(entity_camera)
    assert entry
    assert entry.unique_id == "abcdef-123456-camera"
    await hass.services.async_call(
        "camera",
        "turn_on",
        {"entity_id": entity_camera},
        blocking=True,
    )
    assert len(mock_fully_kiosk.enableMotionDetection.mock_calls) == 1
    await hass.services.async_call(
        "camera",
        "turn_off",
        {"entity_id": entity_camera},
        blocking=True,
    )
    assert len(mock_fully_kiosk.disableMotionDetection.mock_calls) == 1


async def test_screenshot_camera(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test the screenshot camera entity."""
    entity_camera = "camera.amazon_fire_screenshot"
    entity = hass.states.get(entity_camera)
    assert entity
    assert entity.state == "idle"
    entry = entity_registry.async_get(entity_camera)
    assert entry
    assert entry.unique_id == "abcdef-123456-screenshot"


async def test_camera_image(
    hass: HomeAssistant,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test getting image from the camera."""
    entity_camera = "camera.amazon_fire_screenshot"
    mock_fully_kiosk.getScreenshot.return_value = b"image_bytes"
    image = await async_get_image(hass, entity_camera)
    assert mock_fully_kiosk.getScreenshot.call_count == 1
    assert image.content == b"image_bytes"
