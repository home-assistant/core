"""Tests for the template repairs platform."""

import attr
import pytest

from homeassistant.components.template.const import DOMAIN
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator

COMPOSITE_ID = "composite00000000000000000000ab"
TEMPLATE_ENTITY_ID = "sensor.my_template"
EXPECTED_DATA_SCHEMA = [
    {
        "description": {"suggested_value": COMPOSITE_ID},
        "name": "device_id",
        "optional": True,
        "required": False,
        "selector": {"device": {"multiple": False}},
    }
]


@pytest.fixture
def split_devices(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> tuple[dr.DeviceEntry, dr.DeviceEntry]:
    """Create two devices which are splits of a pre-migration composite device."""
    entry_1 = MockConfigEntry(domain="itg1")
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(domain="itg2")
    entry_2.add_to_hass(hass)
    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id,
        identifiers={("itg1", "1")},
        name="Split device 1",
    )
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id,
        identifiers={("itg2", "1")},
        name="Split device 2",
    )
    device_registry.devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=COMPOSITE_ID
    )
    device_registry.devices[device_2.id] = attr.evolve(
        device_2, composite_device_id=COMPOSITE_ID
    )
    return device_registry.devices[device_1.id], device_registry.devices[device_2.id]


async def _setup_template_entry(
    hass: HomeAssistant, device_id: str | None
) -> MockConfigEntry:
    """Set up a sensor template config entry linked to a device."""
    options = {
        "name": "My template",
        "state": "{{10}}",
        "template_type": "sensor",
    }
    if device_id is not None:
        options[CONF_DEVICE_ID] = device_id
    template_config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options=options,
        title="My template",
    )
    template_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()
    return template_config_entry


@pytest.mark.usefixtures("split_devices")
async def test_composite_device_id_creates_issue(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a composite device id in the config entry options creates an issue."""
    entry = await _setup_template_entry(hass, COMPOSITE_ID)

    issue = issue_registry.async_get_issue(
        DOMAIN, f"composite_device_id_{entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_placeholders == {"name": "My template"}

    # The template entity is not linked to the composite device
    entity_entry = entity_registry.async_get(TEMPLATE_ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.device_id is None


async def test_live_device_id_no_issue(
    hass: HomeAssistant,
    split_devices: tuple[dr.DeviceEntry, dr.DeviceEntry],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a live device id in the config entry options creates no issue."""
    entry = await _setup_template_entry(hass, split_devices[0].id)

    assert not issue_registry.async_get_issue(
        DOMAIN, f"composite_device_id_{entry.entry_id}"
    )


@pytest.mark.usefixtures("split_devices")
async def test_no_device_id_no_issue(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a config entry without a device id creates no issue."""
    entry = await _setup_template_entry(hass, None)

    assert not issue_registry.async_get_issue(
        DOMAIN, f"composite_device_id_{entry.entry_id}"
    )


@pytest.mark.parametrize(
    ("pick_device", "expected_device_key_in_options"),
    [
        pytest.param(True, True, id="pick_device"),
        pytest.param(False, False, id="unlink"),
    ],
)
async def test_composite_device_id_repair_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    split_devices: tuple[dr.DeviceEntry, dr.DeviceEntry],
    entity_registry: er.EntityRegistry,
    issue_registry: ir.IssueRegistry,
    pick_device: bool,
    expected_device_key_in_options: bool,
) -> None:
    """Test fixing a composite device id via the repair flow."""
    device_1 = split_devices[0]
    picked_device_id = device_1.id if pick_device else None
    entry = await _setup_template_entry(hass, COMPOSITE_ID)
    issue_id = f"composite_device_id_{entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "select_device"
    assert result["description_placeholders"] == {"name": "My template"}
    assert result["data_schema"] == EXPECTED_DATA_SCHEMA

    user_input = {CONF_DEVICE_ID: picked_device_id} if pick_device else {}
    result = await process_repair_fix_flow(client, result["flow_id"], json=user_input)
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert (CONF_DEVICE_ID in entry.options) == expected_device_key_in_options
    assert entry.options.get(CONF_DEVICE_ID) == picked_device_id
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)

    entity_entry = entity_registry.async_get(TEMPLATE_ENTITY_ID)
    assert entity_entry is not None
    assert entity_entry.device_id == picked_device_id


async def test_composite_device_id_repair_flow_ambiguity_not_resolved(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    split_devices: tuple[dr.DeviceEntry, dr.DeviceEntry],
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the form is shown again if the submitted device is not a real device."""
    device_1 = split_devices[0]
    entry = await _setup_template_entry(hass, COMPOSITE_ID)
    issue_id = f"composite_device_id_{entry.entry_id}"

    assert await async_setup_component(hass, "repairs", {})
    await hass.async_block_till_done()
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert result["type"] == FlowResultType.FORM

    # Submitting the suggested composite device id does not resolve the ambiguity
    result = await process_repair_fix_flow(
        client, result["flow_id"], json={CONF_DEVICE_ID: COMPOSITE_ID}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "select_device"
    assert result["data_schema"] == EXPECTED_DATA_SCHEMA
    assert entry.options[CONF_DEVICE_ID] == COMPOSITE_ID
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    result = await process_repair_fix_flow(
        client, result["flow_id"], json={CONF_DEVICE_ID: device_1.id}
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()

    assert entry.options[CONF_DEVICE_ID] == device_1.id
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


@pytest.mark.usefixtures("split_devices")
async def test_issue_deleted_on_entry_removal(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue is deleted when the config entry is removed."""
    entry = await _setup_template_entry(hass, COMPOSITE_ID)
    issue_id = f"composite_device_id_{entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


@pytest.mark.usefixtures("split_devices")
async def test_issue_deleted_when_device_fixed_in_options(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the issue is deleted on reload after the device id was corrected."""
    entry = await _setup_template_entry(hass, COMPOSITE_ID)
    issue_id = f"composite_device_id_{entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    other_entry = MockConfigEntry(domain="itg3")
    other_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=other_entry.entry_id, identifiers={("itg3", "1")}
    )
    hass.config_entries.async_update_entry(
        entry, options={**entry.options, CONF_DEVICE_ID: device.id}
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
