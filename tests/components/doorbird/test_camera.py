"""Test DoorBird cameras."""

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.camera import (
    CameraState,
    async_get_image,
    async_get_stream_source,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import mock_not_found_exception
from .conftest import DoorbirdMockerType


async def test_doorbird_cameras(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the doorbird cameras."""
    doorbird_entry = await doorbird_mocker()
    live_camera_entity_id = "camera.mydoorbird_live"
    assert hass.states.get(live_camera_entity_id).state == CameraState.IDLE
    last_motion_camera_entity_id = "camera.mydoorbird_last_motion"
    assert hass.states.get(last_motion_camera_entity_id).state == CameraState.IDLE
    last_ring_camera_entity_id = "camera.mydoorbird_last_ring"
    assert hass.states.get(last_ring_camera_entity_id).state == CameraState.IDLE
    assert await async_get_stream_source(hass, live_camera_entity_id) is not None
    api = doorbird_entry.api
    api.get_image.side_effect = mock_not_found_exception()
    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, live_camera_entity_id)
    api.get_image.side_effect = TimeoutError()
    with pytest.raises(HomeAssistantError):
        await async_get_image(hass, live_camera_entity_id)
    api.get_image.side_effect = None
    assert (await async_get_image(hass, live_camera_entity_id)).content == b"image"
    api.get_image.return_value = b"notyet"
    # Ensure rate limit works
    assert (await async_get_image(hass, live_camera_entity_id)).content == b"image"

    freezer.tick(60)
    assert (await async_get_image(hass, live_camera_entity_id)).content == b"notyet"
