"""Test the Opower repairs."""

from homeassistant.components.opower.const import DOMAIN
from homeassistant.components.recorder import Recorder
from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.components.repairs import (
    async_process_repairs_platforms,
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from tests.typing import ClientSessionGenerator


async def test_unsupported_utility_fix_flow(
    recorder_mock: Recorder,
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the unsupported utility fix flow."""
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {REPAIRS_DOMAIN: {}})

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "utility": "Unsupported Utility",
            "username": "test-user",
            "password": "test-password",
        },
        title="My Unsupported Utility",
    )
    mock_config_entry.add_to_hass(hass)

    # Setting up the component with an unsupported utility should fail and create an issue
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    # Verify the issue was created correctly
    issue_id = f"unsupported_utility_{mock_config_entry.entry_id}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == "unsupported_utility"
    assert issue.is_fixable is True
    assert issue.data == {
        "entry_id": mock_config_entry.entry_id,
        "utility": "Unsupported Utility",
        "title": "My Unsupported Utility",
    }

    await async_process_repairs_platforms(hass)
    http_client = await hass_client()

    # Start the repair flow
    data = await start_repair_fix_flow(http_client, DOMAIN, issue_id)
    flow_id = data["flow_id"]

    # The flow should go directly to the confirm step
    assert data["step_id"] == "confirm"
    assert data["description_placeholders"] == {
        "utility": "Unsupported Utility",
        "title": "My Unsupported Utility",
    }

    # Submit the confirmation form
    data = await process_repair_fix_flow(http_client, flow_id, json={})

    # The flow should complete and create an empty entry, signaling success
    assert data["type"] == "create_entry"

    await hass.async_block_till_done()

    # Check that the config entry has been removed
    assert hass.config_entries.async_get_entry(mock_config_entry.entry_id) is None
    # Check that the issue has been resolved
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)
