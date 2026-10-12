"""Test DoorBird cameras."""

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.camera import (
    CameraState,
    async_get_image,
    async_get_stream_source,
    get_camera_from_entity_id,
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


@pytest.mark.parametrize(
    ("entity_id", "supports_two_way_audio", "additional_stream_sources"),
    [
        pytest.param(
            "camera.mydoorbird_live",
            True,
            [
                "http://friend:password@1.2.3.4:80/bha-api/audio-receive.cgi",
                "doorbird://friend:password@1.2.3.4:80",
            ],
            id="live",
        ),
        pytest.param("camera.mydoorbird_last_ring", False, [], id="last_ring"),
        pytest.param("camera.mydoorbird_last_motion", False, [], id="last_motion"),
    ],
)
async def test_doorbird_camera_audio(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    entity_id: str,
    supports_two_way_audio: bool,
    additional_stream_sources: list[str],
) -> None:
    """Test only the live camera provides the audio sources for two way audio."""
    await doorbird_mocker()
    camera = get_camera_from_entity_id(hass, entity_id)
    assert camera.supports_two_way_audio is supports_two_way_audio
    assert await camera.additional_stream_sources() == additional_stream_sources
