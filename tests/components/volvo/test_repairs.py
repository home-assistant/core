"""Test the Volvo repairs."""

from collections.abc import Awaitable, Callable

import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.components.repairs import (
    process_repair_fix_flow,
    start_repair_fix_flow,
)
from pytest_homeassistant.typing import ClientSessionGenerator

from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN, FlowType
from homeassistant.components.volvo.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from .const import CLIENT_ID, CLIENT_SECRET, LEGACY_CLIENT_ID

pytestmark = [
    pytest.mark.parametrize("client_id", [LEGACY_CLIENT_ID]),
    pytest.mark.usefixtures("mock_api"),
]


@pytest.fixture(autouse=True)
async def setup_repairs(hass: HomeAssistant) -> None:
    """Set up the repairs integration."""
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {})


async def test_volvoid_migration_repair_new_reauth(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    setup_integration: Callable[[], Awaitable[bool]],
) -> None:
    """Test that the repair continues in a new reauth flow of the entry."""
    issue_id = f"volvoid_migration_{mock_config_entry.entry_id}"
    assert await setup_integration()
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET), "volvo_new"
    )

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"

    result = await process_repair_fix_flow(client, result["flow_id"], json={})
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_started"

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
    assert result["next_flow"] == [FlowType.CONFIG_FLOW, flows[0]["flow_id"]]
    # Removed by the reload after a successful reauth instead
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None


async def test_volvoid_migration_repair_existing_reauth(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    mock_config_entry: MockConfigEntry,
    setup_integration: Callable[[], Awaitable[bool]],
) -> None:
    """Test that the repair continues in the existing reauth flow of the entry."""
    issue_id = f"volvoid_migration_{mock_config_entry.entry_id}"
    assert await setup_integration()
    await async_import_client_credential(
        hass, DOMAIN, ClientCredential(CLIENT_ID, CLIENT_SECRET), "volvo_new"
    )
    reauth_result = await mock_config_entry.start_reauth_flow(hass)

    client = await hass_client()
    result = await start_repair_fix_flow(client, DOMAIN, issue_id)
    result = await process_repair_fix_flow(client, result["flow_id"], json={})
    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_started"
    assert result["next_flow"] == [FlowType.CONFIG_FLOW, reauth_result["flow_id"]]

    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1
    # Removed by the reload after a successful reauth instead
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None


async def test_volvoid_migration_repair_no_new_credential(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    setup_integration: Callable[[], Awaitable[bool]],
) -> None:
    """Test that the repair doesn't start reauth without a new credential."""
    assert await setup_integration()

    client = await hass_client()
    result = await start_repair_fix_flow(
        client, DOMAIN, f"volvoid_migration_{mock_config_entry.entry_id}"
    )
    result = await process_repair_fix_flow(client, result["flow_id"], json={})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["errors"] == {"base": "no_new_credential"}
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
