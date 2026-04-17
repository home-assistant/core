"""Test Matter vacuum."""

from unittest.mock import MagicMock, call

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.matter.vacuum import MatterVacuum
from homeassistant.components.vacuum import DOMAIN as VACUUM_DOMAIN, Segment
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


@pytest.mark.parametrize("node_fixture", ["mock_vacuum_cleaner"])
async def test_vacuum_silent_reindex_same_names(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test re-indexing detection: same room names, shifted areaIDs.

    Some Matter vacuums (e.g. commissioned into multiple fabrics) re-emit
    SupportedAreas with different areaIDs on operational-state transitions.
    The named room multiset is invariant, so no repair should be raised and
    last_seen_segments should be silently updated to the new IDs.
    """
    entity_id = "vacuum.mock_vacuum"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    # Fixture reports ids {7, 1234567, 2290649224} with names
    # "My Location A"/"B"/"C". Seed last_seen with the same three names
    # but DIFFERENT ids to simulate a past state before the device
    # re-indexed.
    entity_registry.async_update_entity_options(
        entity_id,
        VACUUM_DOMAIN,
        {
            "last_seen_segments": [
                {"id": "100", "name": "My Location A", "group": None},
                {"id": "200", "name": "My Location B", "group": None},
                {"id": "300", "name": "My Location C", "group": None},
            ]
        },
    )

    set_node_attribute(matter_node, 1, 97, 4, 0x02)
    await trigger_subscription_callback(hass, matter_client)

    # No repair should have been created.
    issue_reg = ir.async_get(hass)
    issue = issue_reg.async_get_issue(
        VACUUM_DOMAIN, f"segments_changed_{entity_entry.id}"
    )
    assert issue is None

    # last_seen_segments should now reflect the current (fixture) ids.
    updated = entity_registry.async_get(entity_id)
    assert updated is not None
    last_seen = updated.options[VACUUM_DOMAIN]["last_seen_segments"]
    assert sorted(s["id"] for s in last_seen) == sorted(["7", "1234567", "2290649224"])
    assert sorted(s["name"] for s in last_seen) == sorted(
        ["My Location A", "My Location B", "My Location C"]
    )


@pytest.mark.parametrize("node_fixture", ["mock_vacuum_cleaner"])
async def test_vacuum_silent_reindex_preserves_names(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """A pure segment ID re-index with unchanged names must not fire a repair.

    This test covers the fixture's current setup, where the segment names are
    unique and only the stored IDs differ from the device's current IDs.
    Duplicate-name correctness of the underlying multiset comparison is
    covered separately in ``test_names_match_duplicate_names``.
    """
    entity_id = "vacuum.mock_vacuum"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    # Build a last_seen list that mirrors the fixture's current segment names
    # while using completely different IDs.
    entity_registry.async_update_entity_options(
        entity_id,
        VACUUM_DOMAIN,
        {
            "last_seen_segments": [
                {"id": "a", "name": "My Location A", "group": None},
                {"id": "b", "name": "My Location B", "group": None},
                {"id": "c", "name": "My Location C", "group": None},
            ]
        },
    )

    set_node_attribute(matter_node, 1, 97, 4, 0x02)
    await trigger_subscription_callback(hass, matter_client)

    issue_reg = ir.async_get(hass)
    issue = issue_reg.async_get_issue(
        VACUUM_DOMAIN, f"segments_changed_{entity_entry.id}"
    )
    assert issue is None


@pytest.mark.parametrize("node_fixture", ["mock_vacuum_cleaner"])
async def test_vacuum_reindex_clears_stale_issue(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """A re-index that restores name equivalence must clear a stale issue.

    Scenario: last_seen has a DIFFERENT name set than current (real
    mismatch) -> repair fires. Then last_seen is updated by the user to
    match the current name set; on the next update cycle the re-index
    detection branch runs, silently persists the new IDs, and the stale
    repair is cleared through the existing _async_check_segments_issues
    callback on the registry update.
    """
    entity_id = "vacuum.mock_vacuum"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    # Seed last_seen with a DIFFERENT name -> first update must raise issue.
    entity_registry.async_update_entity_options(
        entity_id,
        VACUUM_DOMAIN,
        {"last_seen_segments": [{"id": "7", "name": "Old location A", "group": None}]},
    )
    set_node_attribute(matter_node, 1, 97, 4, 0x02)
    await trigger_subscription_callback(hass, matter_client)

    issue_reg = ir.async_get(hass)
    issue_id = f"segments_changed_{entity_entry.id}"
    assert issue_reg.async_get_issue(VACUUM_DOMAIN, issue_id) is not None

    # User "accepts" new mapping: last_seen now has current names with
    # DIFFERENT ids. The next device update must:
    # - detect re-indexing (name-multiset equal),
    # - silently persist current ids,
    # - NOT raise a new issue,
    # - AND clear the stale issue via _async_check_segments_issues.
    entity_registry.async_update_entity_options(
        entity_id,
        VACUUM_DOMAIN,
        {
            "last_seen_segments": [
                {"id": "x1", "name": "My Location A", "group": None},
                {"id": "x2", "name": "My Location B", "group": None},
                {"id": "x3", "name": "My Location C", "group": None},
            ]
        },
    )
    set_node_attribute(matter_node, 1, 97, 4, 0x00)
    await trigger_subscription_callback(hass, matter_client)

    assert issue_reg.async_get_issue(VACUUM_DOMAIN, issue_id) is None


def test_names_match_duplicate_names() -> None:
    """``MatterVacuum._names_match`` must treat names as a multiset.

    - Two rooms with the same name and different IDs on both sides are equal.
    - Dropping one of two duplicate-name rooms breaks equality.
    - Mixed None/str group values must not raise (Counter-based comparison).
    """
    current = {
        "1": Segment(id="1", name="Bedroom"),
        "2": Segment(id="2", name="Bedroom"),
        "3": Segment(id="3", name="Kitchen"),
    }
    last_seen = {
        "10": Segment(id="10", name="Bedroom"),
        "20": Segment(id="20", name="Bedroom"),
        "30": Segment(id="30", name="Kitchen"),
    }
    assert MatterVacuum._names_match(current, last_seen)

    # Drop one Bedroom -> multiset differs -> not equal.
    current_missing_bedroom = {
        "1": Segment(id="1", name="Bedroom"),
        "3": Segment(id="3", name="Kitchen"),
    }
    assert not MatterVacuum._names_match(current_missing_bedroom, last_seen)

    # Mixed None/str group values on same name must compare without TypeError.
    current_mixed = {
        "1": Segment(id="1", name="Bedroom", group=None),
        "2": Segment(id="2", name="Bedroom", group="guest"),
    }
    last_seen_mixed = {
        "a": Segment(id="a", name="Bedroom", group="guest"),
        "b": Segment(id="b", name="Bedroom", group=None),
    }
    assert MatterVacuum._names_match(current_mixed, last_seen_mixed)

    # Same names but group values differ -> not equal.
    current_group_differs = {
        "1": Segment(id="1", name="Bedroom", group=None),
        "2": Segment(id="2", name="Bedroom", group=None),
    }
    assert not MatterVacuum._names_match(current_group_differs, last_seen_mixed)


@pytest.mark.parametrize("node_fixture", ["mock_vacuum_cleaner"])
async def test_vacuum_silent_reindex_remaps_area_mapping(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Re-indexing with area_mapping configured must atomically remap IDs.

    The fixture reports segments named ``My Location A/B/C`` with unique IDs.
    Seeding ``last_seen_segments`` with the same names but different IDs and
    an ``area_mapping`` that references those seeded IDs simulates a stored
    state from before the device re-indexed its areas. On the next
    subscription callback the detection logic must rewrite both
    ``last_seen_segments`` and ``area_mapping`` to use the current device IDs
    in a single atomic update, so a later ``vacuum.clean_area`` call resolves
    to IDs the device still accepts.
    """
    entity_id = "vacuum.mock_vacuum"
    entity_entry = entity_registry.async_get(entity_id)
    assert entity_entry is not None

    entity_registry.async_update_entity_options(
        entity_id,
        VACUUM_DOMAIN,
        {
            "last_seen_segments": [
                {"id": "100", "name": "My Location A", "group": None},
                {"id": "200", "name": "My Location B", "group": None},
                {"id": "300", "name": "My Location C", "group": None},
            ],
            "area_mapping": {
                "area_kitchen": ["100"],
                "area_living": ["200", "300"],
            },
        },
    )

    set_node_attribute(matter_node, 1, 97, 4, 0x02)
    await trigger_subscription_callback(hass, matter_client)

    # No repair created.
    issue_reg = ir.async_get(hass)
    assert (
        issue_reg.async_get_issue(VACUUM_DOMAIN, f"segments_changed_{entity_entry.id}")
        is None
    )

    updated = entity_registry.async_get(entity_id)
    assert updated is not None
    options = updated.options[VACUUM_DOMAIN]

    # last_seen_segments now use fixture IDs.
    assert {s["id"] for s in options["last_seen_segments"]} == {
        "7",
        "1234567",
        "2290649224",
    }
    # area_mapping has been translated to fixture IDs.
    assert options["area_mapping"] == {
        "area_kitchen": ["7"],
        "area_living": ["1234567", "2290649224"],
    }


def test_build_id_translation_pairs_by_name_multiset() -> None:
    """``_build_id_translation`` pairs old and new IDs by (name, group)."""
    last_seen = [
        Segment(id="10", name="Kitchen"),
        Segment(id="20", name="Bedroom"),
        Segment(id="30", name="Bedroom"),
    ]
    current = {
        "1": Segment(id="1", name="Kitchen"),
        "2": Segment(id="2", name="Bedroom"),
        "3": Segment(id="3", name="Bedroom"),
    }

    translation = MatterVacuum._build_id_translation(last_seen, current)

    assert translation["10"] == "1"
    # Duplicate-name pairs follow list order - deterministic but arbitrary.
    assert {translation["20"], translation["30"]} == {"2", "3"}


def test_try_remap_area_mapping_happy_path() -> None:
    """Straightforward remap with unique names returns translated mapping."""
    last_seen = [
        Segment(id="10", name="Kitchen"),
        Segment(id="20", name="Living"),
    ]
    translation = {"10": "1", "20": "2"}
    area_mapping = {"area_kitchen": ["10"], "area_living": ["20"]}

    remapped = MatterVacuum._try_remap_area_mapping(
        area_mapping, translation, last_seen
    )

    assert remapped == {"area_kitchen": ["1"], "area_living": ["2"]}


def test_try_remap_area_mapping_duplicate_name_returns_none() -> None:
    """Remap refuses to guess when a user-mapped ID has a duplicate name."""
    last_seen = [
        Segment(id="60", name="Bedroom"),
        Segment(id="70", name="Bedroom"),
        Segment(id="80", name="Kitchen"),
    ]
    translation = {"60": "6", "70": "7", "80": "8"}
    # area_mapping references one of the two "Bedroom" IDs - ambiguous since
    # pairing 60 -> 6 vs 60 -> 7 is arbitrary.
    area_mapping = {"area_kids": ["60"]}

    remapped = MatterVacuum._try_remap_area_mapping(
        area_mapping, translation, last_seen
    )

    assert remapped is None


def test_try_remap_area_mapping_stale_reference_returns_none() -> None:
    """Remap returns None when area_mapping references an unknown old ID."""
    last_seen = [Segment(id="10", name="Kitchen")]
    translation = {"10": "1"}
    area_mapping = {"area_x": ["999"]}  # never existed in last_seen

    remapped = MatterVacuum._try_remap_area_mapping(
        area_mapping, translation, last_seen
    )

    assert remapped is None
