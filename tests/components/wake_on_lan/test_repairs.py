"""Test repairs for Wake on LAN."""

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

from icmplib import Host
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import ClientSessionGenerator, WebSocketGenerator

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.wake_on_lan.const import DOMAIN
from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    entity_registry as er,
    label_registry as lr,
)
from homeassistant.setup import async_setup_component

FULL_CONFIG = {
    "platform": "wake_on_lan",
    "name": "Test",
    "mac": "00-01-02-03-04-05",
    "host": "somehostname.local",
    "turn_off": [
        {
            "action": "input_number.increment",
            "target": {"entity_id": "input_number.number"},
        }
    ],
    "broadcast_address": "255.255.255.255",
    "broadcast_port": "1",
}
MINIMAL_CONFIG = {
    "platform": "wake_on_lan",
    "mac": "00-01-02-03-04-05",
}
NO_HOST_CONFIG = {
    "platform": "wake_on_lan",
    "name": "Test",
    "mac": "00-01-02-03-04-05",
    "turn_off": [
        {
            "action": "input_number.increment",
            "target": {"entity_id": "input_number.number"},
        }
    ],
}
DELAY_CONFIG = {
    "platform": "wake_on_lan",
    "name": "Test",
    "mac": "00-01-02-03-04-05",
    "turn_off": [
        {"delay": "00:00:05"},
        {
            "action": "input_number.set_value",
            "target": {"entity_id": "input_number.number"},
            "data": {"value": "{{ states('input_number.other') }}"},
        },
    ],
}
NO_TURN_OFF_CONFIG = {
    "platform": "wake_on_lan",
    "name": "Test",
    "mac": "00-01-02-03-04-05",
    "host": "somehostname.local",
    "broadcast_address": "255.255.255.255",
    "broadcast_port": "1",
}


@pytest.fixture
def mock_yaml_config() -> Generator[MagicMock]:
    """Mock the YAML configuration read by the repair flow."""
    with patch("homeassistant.config.load_yaml_config_file") as mock_load:
        yield mock_load


async def test_full_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    mock_yaml_config: MagicMock,
) -> None:
    """Test fixing with a full config."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {SWITCH_DOMAIN: FULL_CONFIG},
    )
    mock_yaml_config.return_value = {SWITCH_DOMAIN: FULL_CONFIG}
    await hass.async_block_till_done()

    state = hass.states.get("switch.test")
    assert state

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"].startswith("migrate_to_template"):
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(client, DOMAIN, issue["issue_id"])

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"mac": "00-01-02-03-04-05"}
    assert data["step_id"] == "migrate"

    with patch(
        "homeassistant.components.ping.helpers.async_ping",
        return_value=Host(address="10.10.10.10", packets_sent=10, rtts=[]),
    ):
        data = await process_repair_fix_flow(client, flow_id, json={})

    assert data["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    # Template switch takes over the entity ID of the WOL switch
    assert entity_registry.async_get("switch.test").platform == "template"
    assert hass.states.get("switch.test")

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"].startswith("migrate_to_template"):
            issue = i
    assert not issue

    ping_config_entries = hass.config_entries.async_entries("ping")
    assert ping_config_entries
    ping_entities = entity_registry.entities.get_entries_for_config_entry_id(
        ping_config_entries[0].entry_id
    )
    assert ping_entities
    ping_entity = ping_entities[0].entity_id

    ping_config_entry = ping_config_entries[0]
    assert ping_config_entry.title == "somehostname.local"
    assert ping_config_entry.options == {
        "host": "somehostname.local",
        "count": 5,
        "consider_home": 180,
    }

    wol_config_entries = hass.config_entries.async_entries("wake_on_lan")
    assert wol_config_entries
    wol_entities = entity_registry.entities.get_entries_for_config_entry_id(
        wol_config_entries[0].entry_id
    )
    assert wol_entities
    wol_entity = wol_entities[0].entity_id

    wol_config_entry = wol_config_entries[0]
    assert wol_config_entry.title == "Wake on LAN 00:01:02:03:04:05"
    assert wol_config_entry.options == {
        "mac": "00:01:02:03:04:05",
        "broadcast_address": "255.255.255.255",
        "broadcast_port": 1,
    }

    template_config_entries = hass.config_entries.async_entries("template")
    assert template_config_entries
    template_entities = entity_registry.entities.get_entries_for_config_entry_id(
        template_config_entries[0].entry_id
    )
    assert template_entities
    assert template_entities[0].original_name == "Test"

    template_config_entry = template_config_entries[0]
    assert template_config_entry.title == "Test"
    assert template_config_entry.options == {
        "template_type": "switch",
        "name": "Test",
        "turn_on": [
            {
                "action": "button.press",
                "target": {"entity_id": wol_entity},
            }
        ],
        "value_template": "{{ is_state('" + ping_entity + "', 'on') }}",
        "turn_off": [
            {
                "action": "input_number.increment",
                "target": {"entity_id": "input_number.number"},
            }
        ],
    }


async def test_minimal_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    mock_yaml_config: MagicMock,
) -> None:
    """Test fixing with minimal configuration."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {SWITCH_DOMAIN: MINIMAL_CONFIG},
    )
    mock_yaml_config.return_value = {SWITCH_DOMAIN: MINIMAL_CONFIG}
    await hass.async_block_till_done()

    state = hass.states.get("switch.wake_on_lan")
    assert state

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"].startswith("migrate_to_template"):
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(client, DOMAIN, issue["issue_id"])

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"mac": "00-01-02-03-04-05"}
    assert data["step_id"] == "migrate"

    with patch(
        "homeassistant.components.ping.helpers.async_ping",
        return_value=Host(address="10.10.10.10", packets_sent=10, rtts=[]),
    ):
        data = await process_repair_fix_flow(client, flow_id, json={})

    assert data["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    # Template switch takes over the entity ID of the WOL switch
    assert entity_registry.async_get("switch.wake_on_lan").platform == "template"
    assert hass.states.get("switch.wake_on_lan")

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"].startswith("migrate_to_template"):
            issue = i
    assert not issue

    wol_config_entries = hass.config_entries.async_entries("wake_on_lan")
    assert wol_config_entries
    wol_entities = entity_registry.entities.get_entries_for_config_entry_id(
        wol_config_entries[0].entry_id
    )
    assert wol_entities
    wol_entity = wol_entities[0].entity_id

    wol_config_entry = wol_config_entries[0]
    assert wol_config_entry.title == "Wake on LAN 00:01:02:03:04:05"
    assert wol_config_entry.options == {
        "mac": "00:01:02:03:04:05",
    }

    template_config_entries = hass.config_entries.async_entries("template")
    assert template_config_entries
    template_entities = entity_registry.entities.get_entries_for_config_entry_id(
        template_config_entries[0].entry_id
    )
    assert template_entities
    assert template_entities[0].original_name == "Wake on LAN"

    template_config_entry = template_config_entries[0]
    assert template_config_entry.title == "Wake on LAN"
    assert template_config_entry.options == {
        "template_type": "switch",
        "name": "Wake on LAN",
        "turn_on": [
            {
                "action": "button.press",
                "target": {"entity_id": wol_entity},
            }
        ],
    }


async def test_no_host_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    mock_yaml_config: MagicMock,
) -> None:
    """Test fixing with a no host configured."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {SWITCH_DOMAIN: NO_HOST_CONFIG},
    )
    mock_yaml_config.return_value = {SWITCH_DOMAIN: NO_HOST_CONFIG}
    await hass.async_block_till_done()

    state = hass.states.get("switch.test")
    assert state

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"].startswith("migrate_to_template"):
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(client, DOMAIN, issue["issue_id"])

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"mac": "00-01-02-03-04-05"}
    assert data["step_id"] == "migrate"

    with patch(
        "homeassistant.components.ping.helpers.async_ping",
        return_value=Host(address="10.10.10.10", packets_sent=10, rtts=[]),
    ):
        data = await process_repair_fix_flow(client, flow_id, json={})

    assert data["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    # Template switch takes over the entity ID of the WOL switch
    assert entity_registry.async_get("switch.test").platform == "template"
    assert hass.states.get("switch.test")

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"].startswith("migrate_to_template"):
            issue = i
    assert not issue

    wol_config_entries = hass.config_entries.async_entries("wake_on_lan")
    assert wol_config_entries
    wol_entities = entity_registry.entities.get_entries_for_config_entry_id(
        wol_config_entries[0].entry_id
    )
    assert wol_entities
    wol_entity = wol_entities[0].entity_id

    wol_config_entry = wol_config_entries[0]
    assert wol_config_entry.title == "Wake on LAN 00:01:02:03:04:05"
    assert wol_config_entry.options == {
        "mac": "00:01:02:03:04:05",
    }

    template_config_entries = hass.config_entries.async_entries("template")
    assert template_config_entries
    template_entities = entity_registry.entities.get_entries_for_config_entry_id(
        template_config_entries[0].entry_id
    )
    assert template_entities
    assert template_entities[0].original_name == "Test"

    template_config_entry = template_config_entries[0]
    assert template_config_entry.title == "Test"
    assert template_config_entry.options == {
        "template_type": "switch",
        "name": "Test",
        "turn_on": [
            {
                "action": "button.press",
                "target": {"entity_id": wol_entity},
            }
        ],
        "turn_off": [
            {
                "action": "input_number.increment",
                "target": {"entity_id": "input_number.number"},
            }
        ],
    }


async def test_no_turn_off_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    mock_yaml_config: MagicMock,
) -> None:
    """Test fixing with no turn off action in config."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {SWITCH_DOMAIN: NO_TURN_OFF_CONFIG},
    )
    mock_yaml_config.return_value = {SWITCH_DOMAIN: NO_TURN_OFF_CONFIG}
    await hass.async_block_till_done()

    state = hass.states.get("switch.test")
    assert state

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"].startswith("migrate_to_template"):
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(client, DOMAIN, issue["issue_id"])

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"mac": "00-01-02-03-04-05"}
    assert data["step_id"] == "migrate"

    with patch(
        "homeassistant.components.ping.helpers.async_ping",
        return_value=Host(address="10.10.10.10", packets_sent=10, rtts=[]),
    ):
        data = await process_repair_fix_flow(client, flow_id, json={})

    assert data["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    # Template switch takes over the entity ID of the WOL switch
    assert entity_registry.async_get("switch.test").platform == "template"
    assert hass.states.get("switch.test")

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"].startswith("migrate_to_template"):
            issue = i
    assert not issue

    ping_config_entries = hass.config_entries.async_entries("ping")
    assert ping_config_entries
    ping_entities = entity_registry.entities.get_entries_for_config_entry_id(
        ping_config_entries[0].entry_id
    )
    assert ping_entities
    ping_entity = ping_entities[0].entity_id

    ping_config_entry = ping_config_entries[0]
    assert ping_config_entry.title == "somehostname.local"
    assert ping_config_entry.options == {
        "host": "somehostname.local",
        "count": 5,
        "consider_home": 180,
    }

    wol_config_entries = hass.config_entries.async_entries("wake_on_lan")
    assert wol_config_entries
    wol_entities = entity_registry.entities.get_entries_for_config_entry_id(
        wol_config_entries[0].entry_id
    )
    assert wol_entities
    wol_entity = wol_entities[0].entity_id

    wol_config_entry = wol_config_entries[0]
    assert wol_config_entry.title == "Wake on LAN 00:01:02:03:04:05"
    assert wol_config_entry.options == {
        "mac": "00:01:02:03:04:05",
        "broadcast_address": "255.255.255.255",
        "broadcast_port": 1,
    }

    template_config_entries = hass.config_entries.async_entries("template")
    assert template_config_entries
    template_entities = entity_registry.entities.get_entries_for_config_entry_id(
        template_config_entries[0].entry_id
    )
    assert template_entities
    assert template_entities[0].original_name == "Test"

    template_config_entry = template_config_entries[0]
    assert template_config_entry.title == "Test"
    assert template_config_entry.options == {
        "template_type": "switch",
        "name": "Test",
        "turn_on": [
            {
                "action": "button.press",
                "target": {"entity_id": wol_entity},
            }
        ],
        "value_template": "{{ is_state('" + ping_entity + "', 'on') }}",
    }


async def test_input_entities_already_exist(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    mock_yaml_config: MagicMock,
) -> None:
    """Test fixing when matching ping and WOL entity already exist.

    Only the Template switch should be created.
    """
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {SWITCH_DOMAIN: FULL_CONFIG},
    )
    mock_yaml_config.return_value = {SWITCH_DOMAIN: FULL_CONFIG}
    await hass.async_block_till_done()

    ping_entry = MockConfigEntry(
        title="somehostname.local",
        domain="ping",
        data={},
        options={
            "host": "somehostname.local",
            "count": 5,
            "consider_home": 180,
        },
        minor_version=2,
    )
    ping_entry.add_to_hass(hass)
    wol_entry = MockConfigEntry(
        title="Wake on LAN 00:01:02:03:04:05",
        domain="wake_on_lan",
        data={},
        options={
            "mac": "00:01:02:03:04:05",
            "broadcast_address": "255.255.255.255",
            "broadcast_port": 1,
        },
    )
    wol_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.ping.helpers.async_ping",
        return_value=Host(address="10.10.10.10", packets_sent=10, rtts=[]),
    ):
        await hass.config_entries.async_setup(ping_entry.entry_id)
    await hass.config_entries.async_setup(wol_entry.entry_id)
    await hass.async_block_till_done(True)

    states = hass.states.async_all()
    # switch.test - WOL YAML switch
    # binary_sensor.somehostname_local - Ping config entry
    # zone.home
    # button.wake_on_lan_00_01_02_03_04_05 - WOL config entry
    assert len(states) == 4

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"].startswith("migrate_to_template"):
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(client, DOMAIN, issue["issue_id"])

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"mac": "00-01-02-03-04-05"}
    assert data["step_id"] == "migrate"

    data = await process_repair_fix_flow(client, flow_id, json={})

    assert data["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    # Template switch takes over the entity ID of the WOL switch
    assert entity_registry.async_get("switch.test").platform == "template"
    assert hass.states.get("switch.test")

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"].startswith("migrate_to_template"):
            issue = i
    assert not issue

    ping_config_entries = hass.config_entries.async_entries("ping")
    assert ping_config_entries
    ping_entities = entity_registry.entities.get_entries_for_config_entry_id(
        ping_config_entries[0].entry_id
    )
    assert ping_entities

    wol_config_entries = hass.config_entries.async_entries("wake_on_lan")
    assert wol_config_entries
    wol_entities = entity_registry.entities.get_entries_for_config_entry_id(
        wol_config_entries[0].entry_id
    )
    assert wol_entities

    template_config_entries = hass.config_entries.async_entries("template")
    assert template_config_entries
    template_entities = entity_registry.entities.get_entries_for_config_entry_id(
        template_config_entries[0].entry_id
    )
    assert template_entities

    states = hass.states.async_all()
    # switch.test - Template switch
    # binary_sensor.somehostname_local - Ping config entry
    # zone.home
    # button.wake_on_lan_00_01_02_03_04_05 - WOL config entry
    assert len(states) == 4


async def test_template_switch_already_exist(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
    mock_yaml_config: MagicMock,
) -> None:
    """Test fixing when also template switch already exist."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {SWITCH_DOMAIN: FULL_CONFIG},
    )
    mock_yaml_config.return_value = {SWITCH_DOMAIN: FULL_CONFIG}
    await hass.async_block_till_done()

    ping_entry = MockConfigEntry(
        title="somehostname.local",
        domain="ping",
        data={},
        options={
            "host": "somehostname.local",
            "count": 5,
            "consider_home": 180,
        },
        minor_version=2,
    )
    ping_entry.add_to_hass(hass)
    wol_entry = MockConfigEntry(
        title="Wake on LAN 00:01:02:03:04:05",
        domain="wake_on_lan",
        data={},
        options={
            "mac": "00:01:02:03:04:05",
            "broadcast_address": "255.255.255.255",
            "broadcast_port": 1,
        },
    )
    wol_entry.add_to_hass(hass)
    template_entry = MockConfigEntry(
        title="Test",
        domain="template",
        data={},
        options={
            "template_type": "switch",
            "name": "Test",
            "turn_on": [
                {
                    "action": "button.press",
                    "target": {"entity_id": "button.wake_on_lan_00_01_02_03_04_05"},
                }
            ],
            "turn_off": [
                {
                    "action": "input_number.increment",
                    "target": {"entity_id": "input_number.number"},
                }
            ],
            "value_template": "{{ is_state('binary_sensor.somehostname_local', 'on') }}",
        },
    )
    template_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.ping.helpers.async_ping",
        return_value=Host(address="10.10.10.10", packets_sent=10, rtts=[]),
    ):
        await hass.config_entries.async_setup(ping_entry.entry_id)
    await hass.config_entries.async_setup(wol_entry.entry_id)
    await hass.config_entries.async_setup(template_entry.entry_id)
    await hass.async_block_till_done(True)

    states = hass.states.async_all()
    # switch.test - WOL YAML switch
    # binary_sensor.somehostname_local - Ping config entry
    # zone.home
    # button.wake_on_lan_00_01_02_03_04_05 - WOL config entry
    # switch.test_2 - Template switch
    assert len(states) == 5

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    assert len(msg["result"]["issues"]) > 0
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"].startswith("migrate_to_template"):
            issue = i
    assert issue is not None

    data = await start_repair_fix_flow(client, DOMAIN, issue["issue_id"])

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"mac": "00-01-02-03-04-05"}
    assert data["step_id"] == "migrate"

    data = await process_repair_fix_flow(client, flow_id, json={})

    assert data["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    # The existing Template switch was not created by the repair, so the WOL
    # switch keeps its entity ID
    assert entity_registry.async_get("switch.test").platform == DOMAIN
    assert hass.states.get("switch.test")

    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()

    assert msg["success"]
    issue = None
    for i in msg["result"]["issues"]:
        if i["issue_id"].startswith("migrate_to_template"):
            issue = i
    assert not issue

    ping_config_entries = hass.config_entries.async_entries("ping")
    assert ping_config_entries
    ping_entities = entity_registry.entities.get_entries_for_config_entry_id(
        ping_config_entries[0].entry_id
    )
    assert ping_entities

    wol_config_entries = hass.config_entries.async_entries("wake_on_lan")
    assert wol_config_entries
    wol_entities = entity_registry.entities.get_entries_for_config_entry_id(
        wol_config_entries[0].entry_id
    )
    assert wol_entities

    template_config_entries = hass.config_entries.async_entries("template")
    assert template_config_entries
    template_entities = entity_registry.entities.get_entries_for_config_entry_id(
        template_config_entries[0].entry_id
    )
    assert template_entities

    states = hass.states.async_all()
    # switch.test - WOL YAML switch
    # binary_sensor.somehostname_local - Ping config entry
    # zone.home
    # button.wake_on_lan_00_01_02_03_04_05 - WOL config entry
    # switch.test_2 - Template switch
    assert len(states) == 5


async def test_turn_off_action_not_json_serializable_when_validated(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    mock_yaml_config: MagicMock,
) -> None:
    """Test the template switch gets the off action from the YAML configuration."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {SWITCH_DOMAIN: DELAY_CONFIG},
    )
    mock_yaml_config.return_value = {SWITCH_DOMAIN: DELAY_CONFIG}
    await hass.async_block_till_done()

    assert hass.states.get("switch.test")

    ws_client = await hass_ws_client(hass)
    client = await hass_client()

    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    issue_ids = {i["issue_id"] for i in msg["result"]["issues"]}
    # Issue is identified by the MAC so it does not depend on the validated config
    assert "migrate_to_template_00:01:02:03:04:05" in issue_ids

    # Issue data only holds values that can be sent as JSON
    await ws_client.send_json(
        {
            "id": 2,
            "type": "repairs/get_issue_data",
            "domain": DOMAIN,
            "issue_id": "migrate_to_template_00:01:02:03:04:05",
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]["issue_data"] == {
        "mac": "00-01-02-03-04-05",
        "name": "Test",
    }

    data = await start_repair_fix_flow(
        client, DOMAIN, "migrate_to_template_00:01:02:03:04:05"
    )
    data = await process_repair_fix_flow(client, data["flow_id"], json={})

    assert data["type"] == FlowResultType.CREATE_ENTRY

    template_config_entries = hass.config_entries.async_entries("template")
    assert len(template_config_entries) == 1
    assert template_config_entries[0].options["turn_off"] == DELAY_CONFIG["turn_off"]


@pytest.mark.parametrize(
    ("yaml_config", "expected_turn_off"),
    [
        pytest.param(
            {"switch other": [{"platform": "template"}, NO_HOST_CONFIG]},
            NO_HOST_CONFIG["turn_off"],
            id="named_switch_key",
        ),
        pytest.param(
            {SWITCH_DOMAIN: [{**NO_HOST_CONFIG, "mac": "aa:bb:cc:dd:ee:ff"}]},
            None,
            id="removed_from_yaml",
        ),
    ],
)
async def test_turn_off_action_lookup(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_yaml_config: MagicMock,
    yaml_config: dict[str, Any],
    expected_turn_off: list[dict[str, Any]] | None,
) -> None:
    """Test the off action is looked up for the matching MAC."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {SWITCH_DOMAIN: NO_HOST_CONFIG},
    )
    mock_yaml_config.return_value = yaml_config
    await hass.async_block_till_done()

    client = await hass_client()
    data = await start_repair_fix_flow(
        client, DOMAIN, "migrate_to_template_00:01:02:03:04:05"
    )
    data = await process_repair_fix_flow(client, data["flow_id"], json={})

    assert data["type"] == FlowResultType.CREATE_ENTRY
    template_config_entries = hass.config_entries.async_entries("template")
    assert len(template_config_entries) == 1
    assert template_config_entries[0].options.get("turn_off") == expected_turn_off


async def test_read_configuration_fails(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_yaml_config: MagicMock,
) -> None:
    """Test the repair aborts when the YAML configuration can't be read."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {SWITCH_DOMAIN: NO_HOST_CONFIG},
    )
    mock_yaml_config.side_effect = HomeAssistantError
    await hass.async_block_till_done()

    client = await hass_client()
    data = await start_repair_fix_flow(
        client, DOMAIN, "migrate_to_template_00:01:02:03:04:05"
    )
    data = await process_repair_fix_flow(client, data["flow_id"], json={})

    assert data["type"] == FlowResultType.ABORT
    assert data["reason"] == "could_not_read_configuration"
    assert not hass.config_entries.async_entries("template")


async def test_template_switch_takes_over_customized_entity(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    area_registry: ar.AreaRegistry,
    label_registry: lr.LabelRegistry,
    mock_yaml_config: MagicMock,
) -> None:
    """Test the Template switch takes over a renamed and customized WOL switch."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {SWITCH_DOMAIN: NO_HOST_CONFIG},
    )
    mock_yaml_config.return_value = {SWITCH_DOMAIN: NO_HOST_CONFIG}
    await hass.async_block_till_done()

    area = area_registry.async_create("Office")
    label = label_registry.async_create("Computers")
    entity_registry.async_update_entity(
        "switch.test",
        new_entity_id="switch.office_pc",
        aliases=["Computer"],
        area_id=area.id,
        categories={"helpers": "category_id"},
        icon="mdi:desktop-tower",
        labels={label.label_id},
        name="Office PC",
    )
    entity_registry.async_update_entity_options(
        "switch.office_pc", "conversation", {"should_expose": True}
    )
    await hass.async_block_till_done()

    client = await hass_client()
    data = await start_repair_fix_flow(
        client, DOMAIN, "migrate_to_template_00:01:02:03:04:05"
    )
    data = await process_repair_fix_flow(client, data["flow_id"], json={})

    assert data["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get_entity_id(SWITCH_DOMAIN, DOMAIN, "00:01:02:03:04:05")
        is None
    )
    template_config_entries = hass.config_entries.async_entries("template")
    assert len(template_config_entries) == 1
    entity_entry = entity_registry.async_get("switch.office_pc")
    assert entity_entry.config_entry_id == template_config_entries[0].entry_id
    assert entity_entry.aliases == ["Computer"]
    assert entity_entry.area_id == area.id
    assert entity_entry.categories == {"helpers": "category_id"}
    assert entity_entry.icon == "mdi:desktop-tower"
    assert entity_entry.labels == {label.label_id}
    assert entity_entry.name == "Office PC"
    assert entity_entry.options["conversation"] == {"should_expose": True}
    assert hass.states.get("switch.office_pc").name == "Office PC"
    assert hass.states.get("switch.test") is None


async def _setup_ping_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an existing Ping config entry for somehostname.local."""
    ping_entry = MockConfigEntry(
        title="somehostname.local",
        domain="ping",
        data={},
        options={"host": "somehostname.local", "count": 5, "consider_home": 180},
        minor_version=2,
    )
    ping_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.ping.helpers.async_ping",
        return_value=Host(address="10.10.10.10", packets_sent=10, rtts=[]),
    ):
        await hass.config_entries.async_setup(ping_entry.entry_id)
    await hass.async_block_till_done()
    return ping_entry


async def test_reuse_disabled_ping_entity(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    mock_yaml_config: MagicMock,
) -> None:
    """Test an existing disabled Ping sensor is reused and enabled.

    The host has surrounding whitespace, which Ping strips when storing it.
    """
    config = {**FULL_CONFIG, "host": " somehostname.local "}
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(hass, SWITCH_DOMAIN, {SWITCH_DOMAIN: config})
    mock_yaml_config.return_value = {SWITCH_DOMAIN: config}
    ping_entry = await _setup_ping_entry(hass)
    entity_registry.async_update_entity(
        "binary_sensor.somehostname_local",
        disabled_by=er.RegistryEntryDisabler.INTEGRATION,
    )

    client = await hass_client()
    data = await start_repair_fix_flow(
        client, DOMAIN, "migrate_to_template_00:01:02:03:04:05"
    )
    data = await process_repair_fix_flow(client, data["flow_id"], json={})

    assert data["type"] == FlowResultType.CREATE_ENTRY
    assert hass.config_entries.async_entries("ping") == [ping_entry]
    assert (
        entity_registry.async_get("binary_sensor.somehostname_local").disabled_by
        is None
    )
    template_config_entries = hass.config_entries.async_entries("template")
    assert len(template_config_entries) == 1
    assert template_config_entries[0].options["value_template"] == (
        "{{ is_state('binary_sensor.somehostname_local', 'on') }}"
    )


async def test_ping_entity_disabled_by_config_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    mock_yaml_config: MagicMock,
) -> None:
    """Test the repair aborts when the Ping sensor's config entry is disabled."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass, SWITCH_DOMAIN, {SWITCH_DOMAIN: FULL_CONFIG}
    )
    mock_yaml_config.return_value = {SWITCH_DOMAIN: FULL_CONFIG}
    ping_entry = await _setup_ping_entry(hass)
    await hass.config_entries.async_set_disabled_by(
        ping_entry.entry_id, ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert (
        entity_registry.async_get("binary_sensor.somehostname_local").disabled_by
        is er.RegistryEntryDisabler.CONFIG_ENTRY
    )

    client = await hass_client()
    data = await start_repair_fix_flow(
        client, DOMAIN, "migrate_to_template_00:01:02:03:04:05"
    )
    data = await process_repair_fix_flow(client, data["flow_id"], json={})

    assert data["type"] == FlowResultType.ABORT
    assert data["reason"] == "could_not_get_ping_entity"
    assert not hass.config_entries.async_entries("template")


async def test_import_already_configured_without_lookup_match(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_yaml_config: MagicMock,
) -> None:
    """Test the repair aborts when an import is already configured but not found."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass, SWITCH_DOMAIN, {SWITCH_DOMAIN: FULL_CONFIG}
    )
    mock_yaml_config.return_value = {SWITCH_DOMAIN: FULL_CONFIG}
    # Ping's duplicate check also looks at data, the repair only at options
    MockConfigEntry(
        domain="ping", data={"host": "somehostname.local"}, options={}
    ).add_to_hass(hass)
    await hass.async_block_till_done()

    client = await hass_client()
    data = await start_repair_fix_flow(
        client, DOMAIN, "migrate_to_template_00:01:02:03:04:05"
    )
    data = await process_repair_fix_flow(client, data["flow_id"], json={})

    assert data["type"] == FlowResultType.ABORT
    assert data["reason"] == "could_not_import_host"
