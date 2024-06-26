"""Test the Fully Kiosk Browser camera platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.camera import async_get_image
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_camera(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_fully_kiosk: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test the camera entity."""
    entity_camera = "camera.amazon_fire"
    entity = hass.states.get(entity_camera)
    assert entity
    assert entity.state == "idle"
    entry = entity_registry.async_get(entity_camera)
    assert entry
    assert entry.unique_id == "abcdef-123456-camera"

    mock_fully_kiosk.getSettings.return_value = {"motionDetection": True}
    await hass.services.async_call(
        "camera",
        "turn_on",
        {"entity_id": entity_camera},
        blocking=True,
    )
    assert len(mock_fully_kiosk.enableMotionDetection.mock_calls) == 1

    mock_fully_kiosk.getCamshot.return_value = b"image_bytes"
    image = await async_get_image(hass, entity_camera)
    assert mock_fully_kiosk.getCamshot.call_count == 1
    assert image.content == b"image_bytes"

    mock_fully_kiosk.getSettings.return_value = {"motionDetection": False}
    await hass.services.async_call(
        "camera",
        "turn_off",
        {"entity_id": entity_camera},
        blocking=True,
    )
    assert len(mock_fully_kiosk.disableMotionDetection.mock_calls) == 1

    with pytest.raises(HomeAssistantError) as error:
        await async_get_image(hass, entity_camera)
    assert error.value.args[0] == "Camera is off"
