"""Test the Eufy Security camera platform."""

from unittest.mock import MagicMock

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_camera_entity(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test camera entity is created."""
    state = hass.states.get("camera.front_door_camera_camera")
    assert state is not None
    assert state.state == "idle"

    # Check entity registry
    entry = entity_registry.async_get("camera.front_door_camera_camera")
    assert entry is not None
    assert entry.unique_id == "T1234567890-camera"


async def test_camera_attributes(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test camera entity attributes."""
    state = hass.states.get("camera.front_door_camera_camera")
    assert state is not None

    attributes = state.attributes
    assert attributes["serial_number"] == "T1234567890"
    assert attributes["station_serial"] == "T0987654321"
    assert attributes["hardware_version"] == "2.2"
    assert attributes["software_version"] == "2.0.7.6"


async def test_camera_device_info(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_camera: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test camera device info."""
    entry = entity_registry.async_get("camera.front_door_camera_camera")
    assert entry is not None
    assert entry.device_id is not None
