"""Tests for the Abode camera device."""

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.abode.const import DOMAIN
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

from tests.common import snapshot_platform


@pytest.fixture(autouse=True)
def mock_getrandbits():
    """Mock camera access token which normally is randomized."""
    with patch(
        "homeassistant.components.camera.SystemRandom.getrandbits",
        return_value=1,
    ):
        yield


async def test_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all entities."""
    config_entry = await setup_platform(hass, CAMERA_DOMAIN)

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


async def test_capture_image(hass: HomeAssistant) -> None:
    """Test the camera capture image service."""
    await setup_platform(hass, CAMERA_DOMAIN)

    with patch("jaraco.abode.devices.camera.Camera.capture") as mock_capture:
        await hass.services.async_call(
            DOMAIN,
            "capture_image",
            {ATTR_ENTITY_ID: "camera.test_cam"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_capture.assert_called_once()


async def test_camera_on(hass: HomeAssistant) -> None:
    """Test the camera turn on service."""
    await setup_platform(hass, CAMERA_DOMAIN)

    with patch("jaraco.abode.devices.camera.Camera.privacy_mode") as mock_capture:
        await hass.services.async_call(
            CAMERA_DOMAIN,
            "turn_on",
            {ATTR_ENTITY_ID: "camera.test_cam"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_capture.assert_called_once_with(False)


async def test_camera_off(hass: HomeAssistant) -> None:
    """Test the camera turn off service."""
    await setup_platform(hass, CAMERA_DOMAIN)

    with patch("jaraco.abode.devices.camera.Camera.privacy_mode") as mock_capture:
        await hass.services.async_call(
            CAMERA_DOMAIN,
            "turn_off",
            {ATTR_ENTITY_ID: "camera.test_cam"},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_capture.assert_called_once_with(True)
