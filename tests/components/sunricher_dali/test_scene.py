"""Test the Sunricher DALI scene platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.scene import DOMAIN as SCENE_DOMAIN, SERVICE_TURN_ON
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import trigger_availability_callback

from tests.common import MockConfigEntry, SnapshotAssertion, snapshot_platform

TEST_SCENE_1_ENTITY_ID = "scene.test_gateway_living_room_evening"
TEST_SCENE_2_ENTITY_ID = "scene.test_gateway_kitchen_bright"
TEST_DIMMER_ENTITY_ID = "light.dimmer_0000_02"
TEST_CCT_ENTITY_ID = "light.cct_0000_03"


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to specify which platforms to test."""
    return [Platform.SCENE]


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
    trigger_availability_callback(mock_scenes[0], False)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_SCENE_1_ENTITY_ID)
    assert state.state == "unavailable"

    # Simulate gateway coming back online
    trigger_availability_callback(mock_scenes[0], True)
    await hass.async_block_till_done()

    state = hass.states.get(TEST_SCENE_1_ENTITY_ID)
    assert state.state != "unavailable"
