"""Test Matter vacuum."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from .common import (
    set_node_attribute,
    snapshot_matter_entities,
    trigger_subscription_callback,
)

from tests.typing import WebSocketGenerator


@pytest.mark.usefixtures("matter_devices")
async def test_vacuum(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test that the correct entities get created for a vacuum device."""
    snapshot_matter_entities(hass, entity_registry, snapshot, Platform.VACUUM)


@pytest.mark.parametrize("node_fixture", ["mock_vacuum_cleaner"])
async def test_vacuum_actions(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test vacuum entity actions."""
    # Fetch translations
    await async_setup_component(hass, "homeassistant", {})
    entity_id = "vacuum.mock_vacuum"
    state = hass.states.get(entity_id)
    assert state

    # test return_to_base action
    await hass.services.async_call(
        "vacuum",
        "return_to_base",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.RvcOperationalState.Commands.GoHome(),
    )
    matter_client.send_device_command.reset_mock()

    # test start action (from idle state)
    await hass.services.async_call(
        "vacuum",
        "start",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 2
    assert matter_client.send_device_command.call_args_list[0] == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.ServiceArea.Commands.SelectAreas(newAreas=[]),
    )
    assert matter_client.send_device_command.call_args_list[1] == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.RvcRunMode.Commands.ChangeToMode(newMode=1),
    )
    matter_client.send_device_command.reset_mock()

    # test resume action (from paused state)
    # first set the operational state to paused
    set_node_attribute(matter_node, 1, 97, 4, 0x02)
    await trigger_subscription_callback(hass, matter_client)

    await hass.services.async_call(
        "vacuum",
        "start",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.RvcOperationalState.Commands.Resume(),
    )
    matter_client.send_device_command.reset_mock()

    # test pause action
    await hass.services.async_call(
        "vacuum",
        "pause",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )

    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.RvcOperationalState.Commands.Pause(),
    )
    matter_client.send_device_command.reset_mock()

    # test stop action
    await hass.services.async_call(
        "vacuum",
        "stop",
        {
            "entity_id": entity_id,
        },
        blocking=True,
    )
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.RvcRunMode.Commands.ChangeToMode(newMode=0),
    )
    matter_client.send_device_command.reset_mock()


@pytest.mark.parametrize("node_fixture", ["mock_vacuum_cleaner"])
async def test_vacuum_updates(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test vacuum entity updates."""
    entity_id = "vacuum.mock_vacuum"
    state = hass.states.get(entity_id)
    assert state
    # confirm initial state is idle (as stored in the fixture)
    assert state.state == "idle"

    # confirm state is 'docked' by setting the operational state to 0x42
    set_node_attribute(matter_node, 1, 97, 4, 0x42)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "docked"

    # confirm state is 'docked' by setting the operational state to 0x41
    set_node_attribute(matter_node, 1, 97, 4, 0x41)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "docked"

    # confirm state is 'returning' by setting the operational state to 0x40
    set_node_attribute(matter_node, 1, 97, 4, 0x40)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "returning"

    # confirm state is 'idle' by setting the operational state to 0x01 (running) but mode is idle
    set_node_attribute(matter_node, 1, 97, 4, 0x01)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "idle"

    # confirm state is 'idle' by setting the operational state to 0x01 (running) but mode is cleaning
    set_node_attribute(matter_node, 1, 97, 4, 0x01)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "idle"

    # confirm state is 'paused' by setting the operational state to 0x02
    set_node_attribute(matter_node, 1, 97, 4, 0x02)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "paused"

    # confirm state is 'cleaning' by setting;
    # - the operational state to 0x00
    # - the run mode is set to a mode which has cleaning tag
    set_node_attribute(matter_node, 1, 97, 4, 0)
    set_node_attribute(matter_node, 1, 84, 1, 1)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "cleaning"

    # confirm state is 'idle' by setting;
    # - the operational state to 0x00
    # - the run mode is set to a mode which has idle tag
    set_node_attribute(matter_node, 1, 97, 4, 0)
    set_node_attribute(matter_node, 1, 84, 1, 0)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "idle"

    # confirm state is 'cleaning' by setting;
    # - the operational state to 0x00
    # - the run mode is set to a mode which has mapping tag
    set_node_attribute(matter_node, 1, 97, 4, 0)
    set_node_attribute(matter_node, 1, 84, 1, 2)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "cleaning"

    # confirm state is 'unknown' by setting;
    # - the operational state to 0x00
    # - the run mode is set to a mode which has neither cleaning or idle tag
    set_node_attribute(matter_node, 1, 97, 4, 0)
    set_node_attribute(matter_node, 1, 84, 1, 5)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "unknown"

    # confirm state is 'error' by setting;
    # - the operational state to 0x03
    set_node_attribute(matter_node, 1, 97, 4, 3)
    await trigger_subscription_callback(hass, matter_client)
    state = hass.states.get(entity_id)
    assert state
    assert state.state == "error"


@pytest.mark.parametrize("node_fixture", ["mock_vacuum_cleaner"])
async def test_vacuum_actions_no_supported_run_modes(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test vacuum entity actions when no supported run modes are available."""
    # Fetch translations
    await async_setup_component(hass, "homeassistant", {})
    entity_id = "vacuum.mock_vacuum"
    state = hass.states.get(entity_id)
    assert state

    # Set empty supported modes to simulate no available run modes
    # RvcRunMode cluster ID is 84, SupportedModes attribute ID is 0
    set_node_attribute(matter_node, 1, 84, 0, [])
    # RvcOperationalState cluster ID is 97, AcceptedCommandList attribute ID is 65529
    set_node_attribute(matter_node, 1, 97, 65529, [])
    await trigger_subscription_callback(hass, matter_client)

    # test start action fails when no supported run modes
    with pytest.raises(
        HomeAssistantError,
        match="No supported run mode found to start the vacuum cleaner",
    ):
        await hass.services.async_call(
            "vacuum",
            "start",
            {
                "entity_id": entity_id,
            },
            blocking=True,
        )

    # test stop action fails when no supported run modes
    with pytest.raises(
        HomeAssistantError,
        match="No supported run mode found to stop the vacuum cleaner",
    ):
        await hass.services.async_call(
            "vacuum",
            "stop",
            {
                "entity_id": entity_id,
            },
            blocking=True,
        )

    component = hass.data["vacuum"]
    entity = component.get_entity(entity_id)
    assert entity is not None

    with pytest.raises(
        HomeAssistantError,
        match="No supported run mode found to start the vacuum cleaner",
    ):
        await entity.async_clean_segments(["7"])

    # Ensure no commands were sent to the device
    assert matter_client.send_device_command.call_count == 0


@pytest.mark.parametrize("node_fixture", ["mock_vacuum_cleaner"])
async def test_vacuum_get_segments(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test vacuum get_segments websocket command."""
    await async_setup_component(hass, "homeassistant", {})
    entity_id = "vacuum.mock_vacuum"
    state = hass.states.get(entity_id)
    assert state

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "vacuum/get_segments", "entity_id": entity_id}
    )

    msg = await client.receive_json()
    assert msg["success"]
    segments = msg["result"]["segments"]
    assert len(segments) == 3
    assert segments[0] == {"id": "7", "name": "My Location A", "group": None}
    assert segments[1] == {"id": "1234567", "name": "My Location B", "group": None}
    assert segments[2] == {"id": "2290649224", "name": "My Location C", "group": None}


@pytest.mark.parametrize("node_fixture", ["roborock_saros_10"])
async def test_vacuum_get_segments_nullable_location_info(
    hass: HomeAssistant,
    matter_node: MatterNode,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test vacuum get_segments handles nullable ServiceArea location info."""
    await async_setup_component(hass, "homeassistant", {})
    assert matter_node

    entity_ids = [state.entity_id for state in hass.states.async_all("vacuum")]
    assert len(entity_ids) == 1
    entity_id = entity_ids[0]
    state = hass.states.get(entity_id)
    assert state

    client = await hass_ws_client(hass)
    await client.send_json_auto_id(
        {"type": "vacuum/get_segments", "entity_id": entity_id}
    )

    msg = await client.receive_json()
    assert msg["success"]
    assert msg["result"]["segments"] == [
        {"id": "1", "name": "Living room", "group": None},
        {"id": "2", "name": "Bathroom", "group": None},
        {"id": "3", "name": "Bedroom", "group": None},
        {"id": "4", "name": "Office", "group": None},
        {"id": "5", "name": "Corridor", "group": None},
    ]


@pytest.mark.parametrize("node_fixture", ["mock_vacuum_cleaner"])
async def test_vacuum_clean_area(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test vacuum clean_area service action."""
    await async_setup_component(hass, "homeassistant", {})
    entity_id = "vacuum.mock_vacuum"
    state = hass.states.get(entity_id)
    assert state

    # Set up area_mapping so the service can map area IDs to segment IDs
    entity_registry.async_update_entity_options(
        entity_id,
        VACUUM_DOMAIN,
        {
            "area_mapping": {"area_1": ["7", "1234567"]},
            "last_seen_segments": [
                {"id": "7", "name": "My Location A", "group": None},
                {"id": "1234567", "name": "My Location B", "group": None},
                {"id": "2290649224", "name": "My Location C", "group": None},
            ],
        },
    )

    # Mock a successful SelectAreasResponse (returns as dict over websocket)
    matter_client.send_device_command.return_value = {
        "status": clusters.ServiceArea.Enums.SelectAreasStatus.kSuccess,
        "statusText": "",
    }

    await hass.services.async_call(
        VACUUM_DOMAIN,
        "clean_area",
        {"entity_id": entity_id, "cleaning_area_id": ["area_1"]},
        blocking=True,
    )

    # Verify both commands were sent: SelectAreas followed by ChangeToMode
    assert matter_client.send_device_command.call_count == 2
    assert matter_client.send_device_command.call_args_list[0] == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.ServiceArea.Commands.SelectAreas(newAreas=[7, 1234567]),
    )
    assert matter_client.send_device_command.call_args_list[1] == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.RvcRunMode.Commands.ChangeToMode(newMode=1),
    )


@pytest.mark.parametrize("node_fixture", ["mock_vacuum_cleaner"])
async def test_vacuum_clean_area_select_areas_failure(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test vacuum clean_area raises error when SelectAreas fails."""
    await async_setup_component(hass, "homeassistant", {})
    entity_id = "vacuum.mock_vacuum"
    state = hass.states.get(entity_id)
    assert state

    # Set up area_mapping so the service can map area IDs to segment IDs
    entity_registry.async_update_entity_options(
        entity_id,
        VACUUM_DOMAIN,
        {
            "area_mapping": {"area_1": ["7", "1234567"]},
            "last_seen_segments": [
                {"id": "7", "name": "My Location A", "group": None},
                {"id": "1234567", "name": "My Location B", "group": None},
                {"id": "2290649224", "name": "My Location C", "group": None},
            ],
        },
    )

    # Mock a failed SelectAreasResponse (returns as dict over websocket)
    matter_client.send_device_command.return_value = {
        "status": clusters.ServiceArea.Enums.SelectAreasStatus.kUnsupportedArea,
        "statusText": "Area 7 not supported",
    }

    with pytest.raises(HomeAssistantError, match="Failed to select areas"):
        await hass.services.async_call(
            VACUUM_DOMAIN,
            "clean_area",
            {"entity_id": entity_id, "cleaning_area_id": ["area_1"]},
            blocking=True,
        )

    # Verify only SelectAreas was sent, ChangeToMode should NOT be sent
    assert matter_client.send_device_command.call_count == 1
    assert matter_client.send_device_command.call_args == call(
        node_id=matter_node.node_id,
        endpoint_id=1,
        command=clusters.ServiceArea.Commands.SelectAreas(newAreas=[7, 1234567]),
    )


@pytest.mark.parametrize("node_fixture", ["mock_vacuum_cleaner"])
async def test_vacuum_no_issue_on_transient_empty_segments(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that no issue is raised when device transiently reports empty segments."""
    entity_id = "vacuum.mock_vacuum"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    entity_registry.async_update_entity_options(
        entity_id,
        VACUUM_DOMAIN,
        {
            "last_seen_segments": [
                {
                    "id": "7",
                    "name": "My Location A",
                    "group": None,
                }
            ]
        },
    )

    # Simulate transient empty SupportedAreas (cluster 336, attribute 0)
    set_node_attribute(matter_node, 1, 336, 0, [])
    await trigger_subscription_callback(hass, matter_client)

    issue_reg = ir.async_get(hass)
    issue = issue_reg.async_get_issue(
        VACUUM_DOMAIN, f"segments_changed_{entity_entry.id}"
    )
    assert issue is None


@pytest.mark.parametrize("node_fixture", ["mock_vacuum_cleaner"])
async def test_vacuum_raise_segments_changed_issue(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test that issue is raised on segments change."""
    entity_id = "vacuum.mock_vacuum"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    entity_registry.async_update_entity_options(
        entity_id,
        VACUUM_DOMAIN,
        {
            "last_seen_segments": [
                {
                    "id": "7",
                    "name": "Old location A",
                    "group": None,
                }
            ]
        },
    )

    set_node_attribute(matter_node, 1, 97, 4, 0x02)
    await trigger_subscription_callback(hass, matter_client)

    issue_reg = ir.async_get(hass)
    issue = issue_reg.async_get_issue(
        VACUUM_DOMAIN, f"segments_changed_{entity_entry.id}"
    )
    assert issue is not None
