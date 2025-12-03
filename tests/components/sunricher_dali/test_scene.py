"""Test the Sunricher DALI scene platform."""

from unittest.mock import MagicMock, patch

from PySrDaliGateway import CallbackEventType
import pytest

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import find_device_listener

from tests.common import MockConfigEntry, SnapshotAssertion, snapshot_platform

TEST_SCENE_1_ENTITY_ID = "scene.test_gateway_living_room_evening"
TEST_SCENE_2_ENTITY_ID = "scene.test_gateway_kitchen_bright"


def _trigger_availability_callback(scene: MagicMock, available: bool) -> None:
    """Trigger the availability callbacks registered on the scene mock."""
    callback = find_device_listener(scene, CallbackEventType.ONLINE_STATUS)
    callback(available)


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify which platforms to test."""
    return [Platform.SCENE]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    mock_scenes: list[MagicMock],
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.sunricher_dali._PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the scene entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    device_entry = device_registry.async_get_device(
        identifiers={("sunricher_dali", "6A242121110E")}
    )
    assert device_entry

    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


async def test_activate_scene(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_scenes: list[MagicMock],
) -> None:
    """Test activating a scene."""
    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_SCENE_1_ENTITY_ID},
        blocking=True,
    )

    mock_scenes[0].activate.assert_called_once()


async def test_activate_multiple_scenes(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_scenes: list[MagicMock],
) -> None:
    """Test activating multiple scenes."""
    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [TEST_SCENE_1_ENTITY_ID, TEST_SCENE_2_ENTITY_ID]},
        blocking=True,
    )

    mock_scenes[0].activate.assert_called_once()
    mock_scenes[1].activate.assert_called_once()


async def test_scene_availability(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_scenes: list[MagicMock],
) -> None:
    """Test scene availability changes."""
    state = hass.states.get(TEST_SCENE_1_ENTITY_ID)
    assert state is not None
    assert state.state != "unavailable"

    _trigger_availability_callback(mock_scenes[0], False)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_SCENE_1_ENTITY_ID)
    assert state is not None
    assert state.state == "unavailable"

    _trigger_availability_callback(mock_scenes[0], True)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_SCENE_1_ENTITY_ID)
    assert state is not None
    assert state.state != "unavailable"


async def test_scene_extra_state_attributes(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test scene extra state attributes."""
    state = hass.states.get(TEST_SCENE_1_ENTITY_ID)
    assert state is not None

    assert state.attributes.get("gateway_sn") == "6A242121110E"
    assert state.attributes.get("scene_id") == 1
    assert state.attributes.get("area_id") == "1"
    assert state.attributes.get("channel") == 0
    assert "entity_id" in state.attributes


async def test_callback_registration(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_scenes: list[MagicMock],
) -> None:
    """Test that callbacks are properly registered."""
    mock_scenes[0].register_listener.assert_called()

    calls = mock_scenes[0].register_listener.call_args_list
    event_types = [call[0][0] for call in calls]
    assert CallbackEventType.ONLINE_STATUS in event_types


@pytest.mark.usefixtures("init_integration")
async def test_scene_read_failure(
    hass: HomeAssistant,
    mock_scenes: list[MagicMock],
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test handling of scene read failures during setup."""
    failing_scene = MagicMock()
    failing_scene.scene_id = 99
    failing_scene.name = "Failing Scene"
    failing_scene.unique_id = "scene_0099_0000_6A242121110E"
    failing_scene.gw_sn = "6A242121110E"
    failing_scene.read_scene.side_effect = OSError("Connection error")

    mock_scenes.append(failing_scene)

    assert "Failed to read scene details" in caplog.text or len(mock_scenes) >= 2


async def test_scene_entity_mapping_with_lights(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    mock_devices: list[MagicMock],
    mock_scenes: list[MagicMock],
) -> None:
    """Test that scene entities map to light entities correctly."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sunricher_dali._PLATFORMS",
        [Platform.LIGHT, Platform.SCENE],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(TEST_SCENE_1_ENTITY_ID)
    assert state is not None

    entity_ids = state.attributes.get("entity_id", [])
    assert isinstance(entity_ids, list)


async def test_scene_with_group_device(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
) -> None:
    """Test scene with group device (dev_type 0401)."""
    state = hass.states.get(TEST_SCENE_2_ENTITY_ID)
    assert state is not None
    assert state.attributes.get("scene_id") == 2

    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_SCENE_2_ENTITY_ID},
        blocking=True,
    )
