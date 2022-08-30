"""Test Prusalink camera."""

from unittest.mock import patch

import pytest

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture(autouse=True)
def setup_camera_platform_only():
    """Only setup camera platform."""
    with patch("homeassistant.components.prusalink.PLATFORMS", [Platform.CAMERA]):
        yield


async def test_camera_no_job(
    hass: HomeAssistant,
    mock_config_entry,
    mock_api,
    hass_client,
) -> None:
    """Test sensors while no job active."""
    assert await async_setup_component(hass, "prusalink", {})
    state = hass.states.get("camera.mock_title_job_preview")
    assert state is not None
    assert state.state == "unavailable"

    client = await hass_client()
    resp = await client.get("/api/camera_proxy/camera.mock_title_job_preview")
    assert resp.status == 500


async def test_camera_active_job(
    hass: HomeAssistant, mock_config_entry, mock_api, mock_job_api_active, hass_client
):
    """Test sensors while no job active."""
    assert await async_setup_component(hass, "prusalink", {})
    state = hass.states.get("camera.mock_title_job_preview")
    assert state is not None
    assert state.state == "idle"

    client = await hass_client()

    with patch("pyprusalink.PrusaLink.get_large_thumbnail", return_value=b"hello"):
        resp = await client.get("/api/camera_proxy/camera.mock_title_job_preview")
        assert resp.status == 200
        assert await resp.read() == b"hello"

    # Make sure we hit cached value.
    with patch("pyprusalink.PrusaLink.get_large_thumbnail", side_effect=ValueError):
        resp = await client.get("/api/camera_proxy/camera.mock_title_job_preview")
        assert resp.status == 200
        assert await resp.read() == b"hello"
