"""Tests for rpi_power repairs."""

from homeassistant.components.rpi_power.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, patch
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator


async def test_repair_flow(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test repair flow."""

    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)
    with patch("homeassistant.components.rpi_power.new_under_voltage", get=True):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id="under_voltage_detected",
    )

    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()

    result = await start_repair_fix_flow(client, DOMAIN, "under_voltage_detected")

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, result["flow_id"], {})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert issue_registry.async_get_issue(DOMAIN, "under_voltage_detected") is None
