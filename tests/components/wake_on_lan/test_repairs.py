"""Test repairs for Wake on LAN."""

from unittest.mock import patch

from icmplib import Host

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.wake_on_lan.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import homeassistant.helpers.entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator, WebSocketGenerator

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
NO_TURN_OFF_CONFIG = {
    "platform": "wake_on_lan",
    "name": "Test",
    "mac": "00-01-02-03-04-05",
    "host": "somehostname.local",
    "broadcast_address": "255.255.255.255",
    "broadcast_port": "1",
}


async def test_full_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test fixing with a full config."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {SWITCH_DOMAIN: FULL_CONFIG},
    )
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

    # Repair does not remove the WOL switch
    state = hass.states.get("switch.test")
    assert state

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
                "target": {"entity_id": ["input_number.number"]},
            }
        ],
    }


async def test_minimal_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test fixing with minimal configuration."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {SWITCH_DOMAIN: MINIMAL_CONFIG},
    )
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

    # Repair does not remove the WOL switch
    state = hass.states.get("switch.wake_on_lan")
    assert state

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
) -> None:
    """Test fixing with a no host configured."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {SWITCH_DOMAIN: NO_HOST_CONFIG},
    )
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

    # Repair does not remove the WOL switch
    state = hass.states.get("switch.test")
    assert state

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
                "target": {"entity_id": ["input_number.number"]},
            }
        ],
    }


async def test_no_turn_off_config(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test fixing with no turn off action in config."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {SWITCH_DOMAIN: NO_TURN_OFF_CONFIG},
    )
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

    # Repair does not remove the WOL switch
    state = hass.states.get("switch.test")
    assert state

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

    # Repair does not remove the WOL switch
    state = hass.states.get("switch.test")
    assert state

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


async def test_template_switch_already_exist(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test fixing when also template switch already exist."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass,
        SWITCH_DOMAIN,
        {SWITCH_DOMAIN: FULL_CONFIG},
    )
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
                    "target": {"entity_id": ["input_number.number"]},
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

    # Repair does not remove the WOL switch
    state = hass.states.get("switch.test")
    assert state

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
