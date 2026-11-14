"""Test the Min/Max integration."""

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.group import DOMAIN as GROUP_DOMAIN
from homeassistant.components.min_max.const import DOMAIN
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component


async def test_setup_migrates_to_groups(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test migrating to group sensors."""
    assert await async_setup_component(hass, "repairs", {})
    hass.states.async_set("sensor.input_one", "10")
    hass.states.async_set("sensor.input_two", "20")

    input_sensors = ["sensor.input_one", "sensor.input_two"]

    min_max_entity_id = "sensor.my_min_max"

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        entry_id="123",
        options={
            "entity_ids": input_sensors,
            "name": "My min_max",
            "round_digits": 2.0,
            "type": "max",
        },
        title="My min_max",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity = entity_registry.async_get(min_max_entity_id)
    assert entity is not None

    issue = issue_registry.async_get_issue(
        DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.breaks_in_ha_version == "2027.5.0"

    ws_client = await hass_ws_client(hass)
    client = await hass_client()
    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]

    data = await start_repair_fix_flow(
        client, DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )
    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"title": "My min_max"}
    assert data["step_id"] == "migrate"

    data = await process_repair_fix_flow(client, flow_id, json={})

    assert data["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    entity = entity_registry.async_get(min_max_entity_id)
    assert entity.config_entry_id is not None
    assert entity.config_entry_id != config_entry.entry_id
    assert entity.unique_id != config_entry.entry_id
    assert entity.platform == GROUP_DOMAIN

    assert len(hass.states.async_all()) == 3
    state = hass.states.get(min_max_entity_id)
    assert state.state == "20.0"

    min_max_config_entries = hass.config_entries.async_entries(DOMAIN)
    assert len(min_max_config_entries) == 0

    config_entry = hass.config_entries.async_entries("group")[0]
    assert config_entry.as_dict() == snapshot(
        exclude=props("created_at", "entry_id", "modified_at")
    )

    hass.states.async_set("sensor.input_two", "30")

    freezer.tick(60 * 5)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    state = hass.states.get(min_max_entity_id)
    assert state.state == "30.0"


@pytest.mark.parametrize(
    ("sensor_type", "expected_state"),
    [
        pytest.param("max", "10.0", id="max"),
        pytest.param("min", "10.0", id="min"),
        pytest.param("mean", "10.0", id="mean"),
        pytest.param("median", "10.0", id="median"),
        pytest.param("range", "0.0", id="range"),
        pytest.param("sum", STATE_UNKNOWN, id="sum"),
    ],
)
async def test_migration_keeps_unavailable_input_behavior(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    sensor_type: str,
    expected_state: str,
) -> None:
    """Test the migrated group sensor handles unavailable inputs like Min/Max."""
    assert await async_setup_component(hass, "repairs", {})
    hass.states.async_set("sensor.input_one", "10")
    hass.states.async_set("sensor.input_two", STATE_UNAVAILABLE)

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_ids": ["sensor.input_one", "sensor.input_two"],
            "name": "My min_max",
            "round_digits": 2.0,
            "type": sensor_type,
        },
        title="My min_max",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client()
    data = await start_repair_fix_flow(
        client, DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )
    data = await process_repair_fix_flow(client, data["flow_id"], json={})
    assert data["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    state = hass.states.get("sensor.my_min_max")
    assert state.state == expected_state


async def test_migrate_helper_is_manually_removed(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test migrating to group sensors with manually removed helper."""
    assert await async_setup_component(hass, "repairs", {})
    hass.states.async_set("sensor.input_one", "10")
    hass.states.async_set("sensor.input_two", "20")

    input_sensors = ["sensor.input_one", "sensor.input_two"]

    min_max_entity_id = "sensor.my_min_max"

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        entry_id="123",
        options={
            "entity_ids": input_sensors,
            "name": "My min_max",
            "round_digits": 2.0,
            "type": "max",
        },
        title="My min_max",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity = entity_registry.async_get(min_max_entity_id)
    assert entity is not None

    issue = issue_registry.async_get_issue(
        DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.breaks_in_ha_version == "2027.5.0"

    ws_client = await hass_ws_client(hass)
    client = await hass_client()
    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]

    data = await start_repair_fix_flow(
        client, DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )
    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"title": "My min_max"}
    assert data["step_id"] == "migrate"

    await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    data = await process_repair_fix_flow(client, flow_id, json={})

    assert data["type"] == FlowResultType.ABORT
    assert data["reason"] == "entity_not_found"
    await hass.async_block_till_done()

    entity = entity_registry.async_get(min_max_entity_id)
    assert not entity


async def test_migrate_helper_broken_config(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test migrating to group sensors with broken config."""
    assert await async_setup_component(hass, "repairs", {})
    hass.states.async_set("sensor.input_one", "10")
    hass.states.async_set("switch.input_two", "20")

    input_sensors = ["sensor.input_one", "switch.input_two"]

    min_max_entity_id = "sensor.my_min_max"

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        entry_id="123",
        options={
            "entity_ids": input_sensors,
            "name": "My min_max",
            "round_digits": 2.0,
            "type": "max",
        },
        title="My min_max",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity = entity_registry.async_get(min_max_entity_id)
    assert entity is not None

    issue = issue_registry.async_get_issue(
        DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.breaks_in_ha_version == "2027.5.0"

    ws_client = await hass_ws_client(hass)
    client = await hass_client()
    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]

    data = await start_repair_fix_flow(
        client, DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )
    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"title": "My min_max"}
    assert data["step_id"] == "migrate"

    data = await process_repair_fix_flow(client, flow_id, json={})

    assert data["type"] == FlowResultType.ABORT
    assert data["reason"] == "could_not_import"
    assert data["description_placeholders"]["error"] == (
        "Entity switch.input_two belongs to domain switch"
        ", expected ['sensor', 'number', 'input_number']"
        " at 'entities[1]'"
    )
    await hass.async_block_till_done()

    entity = entity_registry.async_get(min_max_entity_id)
    assert entity
    assert entity.config_entry_id == config_entry.entry_id
    assert entity.platform == DOMAIN


async def test_issue_is_deleted_on_removal(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test issue is removed on config entry removal."""
    assert await async_setup_component(hass, "repairs", {})
    hass.states.async_set("sensor.input_one", "10")
    hass.states.async_set("sensor.input_two", "20")

    input_sensors = ["sensor.input_one", "sensor.input_two"]

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        entry_id="123",
        options={
            "entity_ids": input_sensors,
            "name": "My min_max",
            "round_digits": 2.0,
            "type": "max",
        },
        title="My min_max",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.breaks_in_ha_version == "2027.5.0"

    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )
    assert issue is None


async def test_issue_is_aborted_on_could_not_start_group(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test migrating to group sensors fails when group setup fails."""
    assert await async_setup_component(hass, "repairs", {})
    hass.states.async_set("sensor.input_one", "10")
    hass.states.async_set("sensor.input_two", "20")

    input_sensors = ["sensor.input_one", "sensor.input_two"]

    min_max_entity_id = "sensor.my_min_max"

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        entry_id="123",
        options={
            "entity_ids": input_sensors,
            "name": "My min_max",
            "round_digits": 2.0,
            "type": "max",
        },
        title="My min_max",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity = entity_registry.async_get(min_max_entity_id)
    assert entity is not None

    issue = issue_registry.async_get_issue(
        DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.breaks_in_ha_version == "2027.5.0"

    ws_client = await hass_ws_client(hass)
    client = await hass_client()
    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]

    data = await start_repair_fix_flow(
        client, DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )
    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"title": "My min_max"}
    assert data["step_id"] == "migrate"

    with (
        patch(
            "homeassistant.components.group.async_setup_entry", return_value=False
        ) as mock_setup_entry,
        patch("homeassistant.components.min_max.repairs.asyncio.sleep"),
    ):
        data = await process_repair_fix_flow(client, flow_id, json={})
        await hass.async_block_till_done()

    assert mock_setup_entry.called
    assert data["type"] == FlowResultType.ABORT

    entity = entity_registry.async_get(min_max_entity_id)
    assert entity.config_entry_id is not None
    assert entity.config_entry_id == config_entry.entry_id
    assert entity.unique_id == config_entry.entry_id
    assert entity.platform == DOMAIN

    assert not hass.config_entries.async_has_entries(GROUP_DOMAIN)


async def test_min_max_restored_when_group_setup_fails(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the Min/Max helper is restored when the group setup fails."""
    assert await async_setup_component(hass, "repairs", {})
    hass.states.async_set("sensor.input_one", "10")
    hass.states.async_set("sensor.input_two", "20")

    input_sensors = ["sensor.input_one", "sensor.input_two"]

    min_max_entity_id = "sensor.my_min_max"

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        entry_id="123",
        options={
            "entity_ids": input_sensors,
            "name": "My min_max",
            "round_digits": 2.0,
            "type": "max",
        },
        title="My min_max",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entity = entity_registry.async_get(min_max_entity_id)
    assert entity is not None

    issue = issue_registry.async_get_issue(
        DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.breaks_in_ha_version == "2027.5.0"

    ws_client = await hass_ws_client(hass)
    client = await hass_client()
    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]

    data = await start_repair_fix_flow(
        client, DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )
    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"title": "My min_max"}
    assert data["step_id"] == "migrate"

    forward_entry_setups = hass.config_entries.async_forward_entry_setups

    async def fail_group_setup(entry: ConfigEntry, platforms: list[Platform]) -> None:
        if entry.domain == GROUP_DOMAIN:
            raise ValueError
        await forward_entry_setups(entry, platforms)

    with (
        patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            side_effect=fail_group_setup,
        ) as mock_load_platforms,
        patch("homeassistant.components.min_max.repairs.asyncio.sleep"),
    ):
        data = await process_repair_fix_flow(client, flow_id, json={})
        await hass.async_block_till_done()

    assert mock_load_platforms.called
    assert data["type"] == FlowResultType.ABORT
    assert data["reason"] == "could_not_start_group_entity"

    assert config_entry.state is ConfigEntryState.LOADED
    assert not hass.config_entries.async_entries(GROUP_DOMAIN)
    entity = entity_registry.async_get(min_max_entity_id)
    assert entity.config_entry_id == config_entry.entry_id
    assert entity.unique_id == config_entry.entry_id
    assert entity.platform == DOMAIN
    assert hass.states.get(min_max_entity_id).state == "20.0"
    assert issue_registry.async_get_issue(
        DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )


async def test_min_max_restored_when_entity_migration_fails(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test the Min/Max entry is set up again if moving its entity fails."""
    assert await async_setup_component(hass, "repairs", {})
    hass.states.async_set("sensor.input_one", "10")
    hass.states.async_set("sensor.input_two", "20")

    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "entity_ids": ["sensor.input_one", "sensor.input_two"],
            "name": "My min_max",
            "round_digits": 2.0,
            "type": "max",
        },
        title="My min_max",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_client()
    data = await start_repair_fix_flow(
        client, DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )
    with (
        patch.object(
            entity_registry, "async_update_entity_platform", side_effect=ValueError
        ),
        patch("homeassistant.components.min_max.repairs.asyncio.sleep"),
    ):
        data = await process_repair_fix_flow(client, data["flow_id"], json={})
        await hass.async_block_till_done()

    assert data["type"] == FlowResultType.ABORT
    assert data["reason"] == "could_not_start_group_entity"
    assert config_entry.state is ConfigEntryState.LOADED
    assert not hass.config_entries.async_entries(GROUP_DOMAIN)
    entity = entity_registry.async_get("sensor.my_min_max")
    assert entity.platform == DOMAIN
    assert hass.states.get("sensor.my_min_max").state == "20.0"
