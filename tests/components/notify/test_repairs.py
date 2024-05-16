"""Test repairs for notify entity component."""

from http import HTTPStatus
from unittest.mock import AsyncMock

from homeassistant.components.notify import (
    DOMAIN as NOTIFY_DOMAIN,
    migrate_notify_issue,
)
from homeassistant.components.repairs.issue_handler import (
    async_process_repairs_platforms,
)
from homeassistant.components.repairs.websocket_api import (
    RepairsFlowIndexView,
    RepairsFlowResourceView,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, MockModule, mock_integration
from tests.typing import ClientSessionGenerator

THERMOSTAT_ID = 0


async def test_notify_migration_repair_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    config_flow_fixture: None,
) -> None:
    """Test the notify service repair flow is triggered."""
    await async_setup_component(hass, NOTIFY_DOMAIN, {})
    await hass.async_block_till_done()
    await async_process_repairs_platforms(hass)

    http_client = await hass_client()
    await hass.async_block_till_done()
    config_entry = MockConfigEntry(domain="test")
    config_entry.add_to_hass(hass)
    mock_integration(
        hass,
        MockModule(
            "test",
            async_setup_entry=AsyncMock(return_value=True),
        ),
    )
    assert await hass.config_entries.async_setup(config_entry.entry_id)

    # Simulate legacy service being used and issue being registered
    migrate_notify_issue(hass, "test", "Test", "2024.12.0")
    await hass.async_block_till_done()
    # Assert the issue is present
    assert issue_registry.async_get_issue(
        domain=NOTIFY_DOMAIN,
        issue_id="migrate_notify_test",
    )
    assert len(issue_registry.issues) == 1

    url = RepairsFlowIndexView.url
    resp = await http_client.post(
        url, json={"handler": NOTIFY_DOMAIN, "issue_id": "migrate_notify_test"}
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    url = RepairsFlowResourceView.url.format(flow_id=flow_id)
    resp = await http_client.post(url)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert data["type"] == "create_entry"
    # Test confirm step in repair flow
    await hass.async_block_till_done()

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(
        domain=NOTIFY_DOMAIN,
        issue_id="migrate_notify_test",
    )
    assert len(issue_registry.issues) == 0
