"""Test the homewizard config flow."""

from unittest.mock import MagicMock, patch

from homewizard_energy.errors import DisabledError

from homeassistant.components.homewizard.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator


async def test_repair_acquires_token(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_homewizardenergy: MagicMock,
    mock_homewizardenergy_v2: MagicMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test repair flow is able to obtain and use token."""

    assert await async_setup_component(hass, "repairs", {})
    await async_process_repairs_platforms(hass)
    client = await hass_client()

    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, unique_id="HWE-BAT_5c2fafabcdef"
    )
    await hass.async_block_till_done()

    with patch("homeassistant.components.homewizard.has_v2_api", return_value=True):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Get active repair flow
    issue_id = f"migrate_to_v2_api_{mock_config_entry.entry_id}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None

    assert issue.data.get("entry_id") == mock_config_entry.entry_id

    mock_homewizardenergy_v2.get_token.side_effect = DisabledError

    result = await start_repair_fix_flow(client, DOMAIN, issue_id)

    flow_id = result["flow_id"]
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, flow_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "authorize"

    # Simulate user not pressing the button
    result = await process_repair_fix_flow(client, flow_id, json={})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "authorize"
    assert result["errors"] == {"base": "authorization_failed"}

    # Simulate user pressing the button and getting a new token
    mock_homewizardenergy_v2.get_token.side_effect = None
    mock_homewizardenergy_v2.get_token.return_value = "cool_token"
    result = await process_repair_fix_flow(client, flow_id, json={})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert mock_config_entry.data[CONF_TOKEN] == "cool_token"
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
