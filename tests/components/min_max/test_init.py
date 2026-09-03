"""Test the Min/Max integration."""

from freezegun.api import FrozenDateTimeFactory
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.group import DOMAIN as GROUP_DOMAIN
from homeassistant.components.min_max.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator, WebSocketGenerator


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

    # Setup the config entry
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

    # Check the entity is registered in the entity registry
    entity = entity_registry.async_get(min_max_entity_id)
    assert entity is not None

    issue = issue_registry.async_get_issue(
        DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.breaks_in_ha_version == "2026.12.0"

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

    # Check the platform is setup correctly
    assert len(hass.states.async_all()) == 3
    state = hass.states.get(min_max_entity_id)
    assert state.state == "20.0"

    # Assert min/max config entry is removed
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

    # Setup the config entry
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

    # Check the entity is registered in the entity registry
    entity = entity_registry.async_get(min_max_entity_id)
    assert entity is not None

    issue = issue_registry.async_get_issue(
        DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.breaks_in_ha_version == "2026.12.0"

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

    # Manually remove the Min/Max helper before repairing
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

    # Setup the config entry
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

    # Check the entity is registered in the entity registry
    entity = entity_registry.async_get(min_max_entity_id)
    assert entity is not None

    issue = issue_registry.async_get_issue(
        DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.breaks_in_ha_version == "2026.12.0"

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
        " @ data['entities'][1]"
    )
    await hass.async_block_till_done()

    # Entity still exists as Min/Max helper as repair failed
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

    # Setup the config entry
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
    assert issue.breaks_in_ha_version == "2026.12.0"

    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    issue = issue_registry.async_get_issue(
        DOMAIN, f"migrate_to_group_sensor-{config_entry.entry_id}"
    )
    assert issue is None
