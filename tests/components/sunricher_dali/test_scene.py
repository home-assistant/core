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
TEST_DIMMER_ENTITY_ID = "light.dimmer_0000_02"
TEST_CCT_ENTITY_ID = "light.cct_0000_03"


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
    mock_scenes: list[MagicMock],
) -> None:
    """Test the scene entities and their attributes."""
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

    state = hass.states.get(TEST_SCENE_1_ENTITY_ID)
    assert state is not None
    # Only entity_id mapping is kept in extra state attributes
    assert "entity_id" in state.attributes


async def test_activate_scenes(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_scenes: list[MagicMock],
) -> None:
    """Test activating single and multiple scenes."""
    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: TEST_SCENE_1_ENTITY_ID},
        blocking=True,
    )
    mock_scenes[0].activate.assert_called_once()

    await hass.services.async_call(
        SCENE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: [TEST_SCENE_1_ENTITY_ID, TEST_SCENE_2_ENTITY_ID]},
        blocking=True,
    )
    assert mock_scenes[0].activate.call_count == 2
    mock_scenes[1].activate.assert_called_once()


async def test_scene_availability(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_scenes: list[MagicMock],
) -> None:
    """Test scene availability changes when gateway goes offline."""
    state = hass.states.get(TEST_SCENE_1_ENTITY_ID)
    assert state is not None
    assert state.state != "unavailable"

    # Simulate gateway going offline
    _trigger_availability_callback(mock_scenes[0], False)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_SCENE_1_ENTITY_ID)
    assert state.state == "unavailable"

    # Simulate gateway coming back online
    _trigger_availability_callback(mock_scenes[0], True)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_SCENE_1_ENTITY_ID)
    assert state.state != "unavailable"


async def test_scene_entity_mapping(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_gateway: MagicMock,
    mock_devices: list[MagicMock],
    mock_scenes: list[MagicMock],
) -> None:
    """Test scene entity mapping with lights and group devices."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.sunricher_dali._PLATFORMS",
        [Platform.LIGHT, Platform.SCENE],
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get(TEST_SCENE_1_ENTITY_ID)
    assert state is not None
    assert isinstance(state.attributes.get("entity_id", []), list)

    state = hass.states.get(TEST_SCENE_2_ENTITY_ID)
    assert state is not None
    assert isinstance(state.attributes.get("entity_id", []), list)
