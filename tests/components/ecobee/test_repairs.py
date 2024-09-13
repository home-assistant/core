"""Test repairs for Ecobee integration."""

from http import HTTPStatus
from unittest.mock import MagicMock

from homeassistant.components.ecobee import DOMAIN
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.repairs import (
    INDEX_VIEW_URL,
    RESOURCE_VIEW_URL,
    async_process_repairs_platforms,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from .common import setup_platform

from tests.typing import ClientSessionGenerator

THERMOSTAT_ID = 0


async def test_ecobee_notify_repair_flow(
    hass: HomeAssistant,
    mock_ecobee: MagicMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the ecobee notify service repair flow is triggered."""
    await setup_platform(hass, NOTIFY_DOMAIN)
    await async_process_repairs_platforms(hass)

    http_client = await hass_client()

    # Simulate legacy service being used
    assert hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        DOMAIN,
        service_data={"message": "It is too cold!", "target": THERMOSTAT_ID},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_ecobee.send_message.assert_called_with(THERMOSTAT_ID, "It is too cold!")
    mock_ecobee.send_message.reset_mock()

    # Assert the issue is present
    assert issue_registry.async_get_issue(
        domain="notify",
        issue_id=f"migrate_notify_{DOMAIN}_{DOMAIN}",
    )
    assert len(issue_registry.issues) == 1

    url = INDEX_VIEW_URL
    resp = await http_client.post(
        url, json={"handler": "notify", "issue_id": f"migrate_notify_{DOMAIN}_{DOMAIN}"}
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    url = RESOURCE_VIEW_URL.format(flow_id=flow_id)
    resp = await http_client.post(url)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert data["type"] == "create_entry"
    # Test confirm step in repair flow
    await hass.async_block_till_done()

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(
        domain="notify",
        issue_id=f"migrate_notify_{DOMAIN}_{DOMAIN}",
    )
    assert len(issue_registry.issues) == 0
