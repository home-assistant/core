"""Test repairs for La Marzocco."""

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.lamarzocco.const import (
    CONF_OFFLINE_MODE,
    CONF_USE_BLUETOOTH,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import async_init_integration


@pytest.mark.usefixtures("mock_lamarzocco")
async def test_missing_bluetooth_token_disable_bluetooth(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the repair flow turns off Bluetooth when the token is missing."""
    assert await async_setup_component(hass, "repairs", {})
    entry = MockConfigEntry(
        title=mock_config_entry.title,
        domain=DOMAIN,
        version=4,
        data=mock_config_entry.data | {CONF_TOKEN: None},
        unique_id=mock_config_entry.unique_id,
    )
    await async_init_integration(hass, entry)
    issue_id = f"missing_bluetooth_token_{entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    client = await hass_client()
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert data["step_id"] == "confirm"
    assert data["description_placeholders"] == {"name": entry.title}

    data = await process_repair_fix_flow(client, data["flow_id"])
    await hass.async_block_till_done()

    assert data["type"] == "create_entry"
    assert entry.options == {CONF_USE_BLUETOOTH: False, CONF_OFFLINE_MODE: False}
    assert entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
