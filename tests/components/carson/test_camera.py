"""Tests for the Carson Camera platform."""
from unittest.mock import patch

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN

from .common import carson_load_fixture, fixture_een_subdomain, setup_platform


async def test_entity_registry(hass, success_requests_mock):
    """Tests that the devices are registered in the entity registry."""
    await setup_platform(hass, CAMERA_DOMAIN)
    entity_registry = await hass.helpers.entity_registry.async_get_registry()

    entry = entity_registry.async_get("camera.camera_name_1")
    assert entry.unique_id == "eagleeye_camera_c0"
    entry = entity_registry.async_get("camera.camera_name_2")
    assert entry.unique_id == "eagleeye_camera_c1"
    entry = entity_registry.async_get("camera.camera_name_3")
    # camera.camera_name_3 does NOT exist
    assert entry is None


async def test_entity_registry_een_option_enabled(hass, success_requests_mock):
    """Tests that the devices are registered in the entity registry."""
    with patch(
        "homeassistant.components.carson.camera.get_list_een_option", return_value=True
    ) as mock_setup:
        await setup_platform(hass, CAMERA_DOMAIN)
        entity_registry = await hass.helpers.entity_registry.async_get_registry()

        entry = entity_registry.async_get("camera.camera_name_1")
        assert entry.unique_id == "eagleeye_camera_c0"
        entry = entity_registry.async_get("camera.camera_name_2")
        assert entry.unique_id == "eagleeye_camera_c1"
        entry = entity_registry.async_get("camera.camera_name_3")
        # camera.camera_name_3 exists
        assert entry.unique_id == "eagleeye_camera_c2"
        assert mock_setup.call_count == 1


async def test_camera_can_be_updated(hass, success_requests_mock):
    """Tests that the camera returns a binary image."""
    await setup_platform(hass, CAMERA_DOMAIN)

    state = hass.states.get("camera.camera_name_1")
    assert state.attributes.get("friendly_name") == "Camera Name 1"

    een_subdomain = fixture_een_subdomain()
    success_requests_mock.get(
        f"https://{een_subdomain}.eagleeyenetworks.com/g/device/list",
        text=carson_load_fixture("een_device_list_update.json"),
    )

    await hass.services.async_call("carson", "update", {})

    await hass.async_block_till_done()

    state = hass.states.get("camera.camera_name_1")
    assert state.attributes.get("friendly_name") == "Camera Name 1 Updated"


async def test_camera_returns_image(hass, success_requests_mock):
    """Test that a camera returns in binary image."""
    await setup_platform(hass, CAMERA_DOMAIN)
    component = hass.data.get(CAMERA_DOMAIN)

    data = b"image as binary data"
    een_subdomain = fixture_een_subdomain()
    success_requests_mock.get(
        f"https://{een_subdomain}.eagleeyenetworks.com/asset/prev/image.jpeg",
        content=data,
    )

    camera = component.get_entity("camera.camera_name_1")

    img = camera.camera_image()

    assert img is not None
    assert data == img


async def test_camera_returns_stream_url(hass, success_requests_mock):
    """Test that the camera returns stream URL."""
    await setup_platform(hass, CAMERA_DOMAIN)
    component = hass.data.get(CAMERA_DOMAIN)

    camera = component.get_entity("camera.camera_name_1")

    een_subdomain = fixture_een_subdomain()
    success_requests_mock.get(
        f"https://{een_subdomain}.eagleeyenetworks.com/g/aaa/isauth", text="true"
    )

    url = await camera.stream_source()

    assert f"https://{een_subdomain}.eagleeyenetworks.com/asset/play/video.flv" in url
    assert "id=" in url
    assert "start_timestamp=" in url
    assert "end_timestamp=" in url
    assert "A=" in url
