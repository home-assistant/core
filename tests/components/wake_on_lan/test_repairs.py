"""Test repairs for Wake on LAN."""

import asyncio
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
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import switch
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.wake_on_lan.const import DOMAIN
from homeassistant.components.wake_on_lan.switch import WolSwitch
from homeassistant.config_entries import ConfigEntryDisabler
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    area_registry as ar,
    entity_registry as er,
    issue_registry as ir,
    label_registry as lr,
)
from homeassistant.setup import async_setup_component

ISSUE_ID = "migrate_to_template_00:01:02:03:04:05"
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


@pytest.mark.parametrize(
    ("config", "entity_id", "description"),
    [
        pytest.param(FULL_CONFIG, "switch.test", "with_ping", id="full"),
        pytest.param(MINIMAL_CONFIG, "switch.wake_on_lan", "no_ping", id="minimal"),
        pytest.param(NO_HOST_CONFIG, "switch.test", "no_ping", id="no_host"),
        pytest.param(NO_TURN_OFF_CONFIG, "switch.test", "with_ping", id="no_turn_off"),
    ],
)
async def test_migrate(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    mock_yaml_config: MagicMock,
    snapshot: SnapshotAssertion,
    config: dict[str, Any],
    entity_id: str,
    description: str,
) -> None:
    """Test migrating a WOL switch to a Template switch."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(hass, SWITCH_DOMAIN, {SWITCH_DOMAIN: config})
    mock_yaml_config.return_value = {SWITCH_DOMAIN: config}
    await hass.async_block_till_done()

    assert entity_registry.async_get(entity_id).platform == DOMAIN
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID)

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
    assert data["description_placeholders"] == {"mac": "00-01-02-03-04-05"}
    assert data["step_id"] == "migrate"

    with patch(
        "homeassistant.components.ping.helpers.async_ping",
        return_value=Host(address="10.10.10.10", packets_sent=10, rtts=[]),
    ):
        data = await process_repair_fix_flow(client, data["flow_id"], json={})

    assert data["type"] == FlowResultType.CREATE_ENTRY
    assert data["description"] == description
    await hass.async_block_till_done()

    # Template switch takes over the entity ID of the WOL switch
    assert entity_registry.async_get(entity_id).platform == "template"
    assert hass.states.get(entity_id)
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None
    assert {
        domain: [
            {"title": entry.title, "options": dict(entry.options)}
            for entry in hass.config_entries.async_entries(domain)
        ]
        for domain in ("ping", DOMAIN, "template")
    } == snapshot


async def test_input_entities_already_exist(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
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

    client = await hass_client()

    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID)

    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"mac": "00-01-02-03-04-05"}
    assert data["step_id"] == "migrate"

    data = await process_repair_fix_flow(client, flow_id, json={})

    assert data["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    # Template switch takes over the entity ID of the WOL switch
    assert entity_registry.async_get("switch.test").platform == "template"
    assert hass.states.get("switch.test")

    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None

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
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
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

    client = await hass_client()

    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID)

    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)

    flow_id = data["flow_id"]
    assert data["description_placeholders"] == {"mac": "00-01-02-03-04-05"}
    assert data["step_id"] == "migrate"

    data = await process_repair_fix_flow(client, flow_id, json={})

    assert data["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    # The existing Template switch was not created by the repair, so the WOL
    # switch keeps its entity ID and the user is told to move references
    assert data["description_placeholders"] == {
        "mac": "00-01-02-03-04-05",
        "entity_id": "switch.test_2",
        "old_entity_id": "switch.test",
    }
    assert entity_registry.async_get("switch.test").platform == DOMAIN
    assert hass.states.get("switch.test")

    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID) is None

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
    issue_registry: ir.IssueRegistry,
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

    # Issue is identified by the MAC so it does not depend on the validated config
    assert issue_registry.async_get_issue(DOMAIN, ISSUE_ID)

    # Issue data only holds values that can be sent as JSON
    await ws_client.send_json(
        {
            "id": 2,
            "type": "repairs/get_issue_data",
            "domain": DOMAIN,
            "issue_id": ISSUE_ID,
        }
    )
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert msg["result"]["issue_data"] == {
        "mac": "00-01-02-03-04-05",
        "name": "Test",
    }

    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
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
    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
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
    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
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
        device_class="outlet",
        icon="mdi:desktop-tower",
        labels={label.label_id},
        name="Office PC",
    )
    entity_registry.async_update_entity_options(
        "switch.office_pc", "conversation", {"should_expose": True}
    )
    entity_registry.async_update_entity(
        "switch.office_pc", hidden_by=er.RegistryEntryHider.USER
    )
    await hass.async_block_till_done()

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
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
    assert entity_entry.device_class == "outlet"
    assert entity_entry.icon == "mdi:desktop-tower"
    assert entity_entry.labels == {label.label_id}
    assert entity_entry.name == "Office PC"
    assert entity_entry.options["conversation"] == {"should_expose": True}
    assert entity_entry.hidden_by is er.RegistryEntryHider.USER
    assert entity_entry.disabled_by is None
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
    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
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
    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
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
    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
    data = await process_repair_fix_flow(client, data["flow_id"], json={})

    assert data["type"] == FlowResultType.ABORT
    assert data["reason"] == "could_not_import_host"


@pytest.mark.parametrize(
    ("disabled_by", "expected_disabled_by"),
    [
        pytest.param(
            er.RegistryEntryDisabler.USER,
            er.RegistryEntryDisabler.USER,
            id="user",
        ),
        pytest.param(er.RegistryEntryDisabler.INTEGRATION, None, id="integration"),
    ],
)
async def test_template_switch_takes_over_disabled_entity(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    mock_yaml_config: MagicMock,
    disabled_by: er.RegistryEntryDisabler,
    expected_disabled_by: er.RegistryEntryDisabler | None,
) -> None:
    """Test only a user disabled WOL switch leaves the Template switch disabled."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass, SWITCH_DOMAIN, {SWITCH_DOMAIN: NO_HOST_CONFIG}
    )
    mock_yaml_config.return_value = {SWITCH_DOMAIN: NO_HOST_CONFIG}
    await hass.async_block_till_done()
    entity_registry.async_update_entity("switch.test", disabled_by=disabled_by)
    await hass.async_block_till_done()

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
    data = await process_repair_fix_flow(client, data["flow_id"], json={})

    assert data["type"] == FlowResultType.CREATE_ENTRY
    entity_entry = entity_registry.async_get("switch.test")
    assert entity_entry.platform == "template"
    assert entity_entry.disabled_by is expected_disabled_by


DELAYED_OFF_CONFIG = {
    "platform": "wake_on_lan",
    "name": "Test",
    "mac": "00-01-02-03-04-05",
    "turn_off": [{"delay": "00:10:00"}],
}


async def test_take_over_entity_id_while_off_script_runs(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    mock_yaml_config: MagicMock,
) -> None:
    """Test the entity ID is taken over while the WOL switch's off script runs.

    Stopping the running script delays the removal of the old state.
    """
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass, SWITCH_DOMAIN, {SWITCH_DOMAIN: DELAYED_OFF_CONFIG}
    )
    mock_yaml_config.return_value = {SWITCH_DOMAIN: DELAYED_OFF_CONFIG}
    await hass.async_block_till_done()
    entity = hass.data[switch.DOMAIN].get_entity("switch.test")
    assert isinstance(entity, WolSwitch)
    assert entity._off_script is not None
    hass.async_create_task(entity._off_script.async_run(context=None))
    await asyncio.sleep(0)
    assert entity._off_script.is_running

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
    data = await process_repair_fix_flow(client, data["flow_id"], json={})

    assert data["type"] == FlowResultType.CREATE_ENTRY
    assert entity_registry.async_get("switch.test").platform == "template"


async def test_take_over_entity_id_old_state_not_removed(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    entity_registry: er.EntityRegistry,
    mock_yaml_config: MagicMock,
) -> None:
    """Test the repair aborts when the old state is not removed in time."""
    assert await async_setup_component(hass, "repairs", {})
    assert await async_setup_component(
        hass, SWITCH_DOMAIN, {SWITCH_DOMAIN: NO_HOST_CONFIG}
    )
    mock_yaml_config.return_value = {SWITCH_DOMAIN: NO_HOST_CONFIG}
    await hass.async_block_till_done()
    never_set = asyncio.Event()

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, ISSUE_ID)
    with (
        patch.object(
            WolSwitch, "async_will_remove_from_hass", side_effect=never_set.wait
        ),
        patch("homeassistant.components.wake_on_lan.repairs.asyncio.sleep"),
    ):
        data = await process_repair_fix_flow(client, data["flow_id"], json={})

    assert data["type"] == FlowResultType.ABORT
    assert data["reason"] == "could_not_take_over_entity_id"
    assert data["description_placeholders"] == {
        "entity_id": "switch.test_2",
        "old_entity_id": "switch.test",
    }
    never_set.set()
    await hass.async_block_till_done()
