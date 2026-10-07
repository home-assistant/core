"""Tests for the Abode camera device."""

from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import MagicMock, patch

from jaraco.abode.helpers import timeline
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.abode.const import DOMAIN
from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import setup_platform

from tests.common import MockConfigEntry, snapshot_platform

CAMERA_ENTITY_ID = "camera.test_cam"


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


@pytest.fixture
def mock_update_image_location() -> Generator[MagicMock]:
    """Mock the camera image location update and skip the image download."""
    with (
        patch(
            "jaraco.abode.devices.camera.Camera.update_image_location"
        ) as mock_update,
        patch("homeassistant.components.abode.camera.AbodeCamera.get_image"),
    ):
        yield mock_update


def _timeline_capture_callbacks(
    config_entry: MockConfigEntry,
) -> list[Callable[[Any], None]]:
    """Return the capture image timeline callbacks registered with jaraco.abode."""
    events = config_entry.runtime_data.abode.events
    return events._timeline_callbacks[timeline.CAPTURE_IMAGE["event_code"]]


async def _fire_capture(
    hass: HomeAssistant, callbacks: list[Callable[[Any], None]]
) -> None:
    """Fire a capture image timeline event from the jaraco.abode thread."""
    for capture_callback in callbacks:
        await hass.async_add_executor_job(capture_callback, timeline.CAPTURE_IMAGE)
    await hass.async_block_till_done()


async def test_timeline_capture_after_entity_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_update_image_location: MagicMock,
) -> None:
    """Test a removed camera no longer handles timeline capture events."""
    config_entry = await setup_platform(hass, CAMERA_DOMAIN)
    callbacks = _timeline_capture_callbacks(config_entry)

    await _fire_capture(hass, callbacks)
    mock_update_image_location.assert_called_once()

    entity_registry.async_remove(CAMERA_ENTITY_ID)
    await hass.async_block_till_done()
    assert hass.states.get(CAMERA_ENTITY_ID) is None

    mock_update_image_location.reset_mock()
    await _fire_capture(hass, callbacks)
    mock_update_image_location.assert_not_called()


async def test_timeline_capture_after_entity_readded(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_update_image_location: MagicMock,
) -> None:
    """Test a re-added camera handles each timeline capture event once."""
    config_entry = await setup_platform(hass, CAMERA_DOMAIN)

    # Changing the entity_id removes and re-adds the same entity object.
    entity_registry.async_update_entity(
        CAMERA_ENTITY_ID, new_entity_id="camera.renamed_cam"
    )
    await hass.async_block_till_done()
    assert hass.states.get("camera.renamed_cam")

    callbacks = _timeline_capture_callbacks(config_entry)
    assert len(callbacks) == 1

    await _fire_capture(hass, callbacks)
    mock_update_image_location.assert_called_once()
