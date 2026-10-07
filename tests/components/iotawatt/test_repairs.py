"""Test repairs for IoTaWatt."""

from unittest.mock import MagicMock

from homeassistant.components.iotawatt.const import CONF_LEGACY_ENERGY, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator


async def test_legacy_energy_fix_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_iotawatt: MagicMock,
    entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the fix flow switches the entry to the lifetime energy sensors."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()
    assert await async_setup_component(hass, "repairs", {})

    issue_id = f"legacy_energy_{entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert data["step_id"] == "confirm"

    data = await process_repair_fix_flow(client, data["flow_id"], json={})
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    assert entry.options == {CONF_LEGACY_ENERGY: False}
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
