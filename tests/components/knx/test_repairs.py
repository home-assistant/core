"""Test repairs for KNX integration."""

from http import HTTPStatus

from homeassistant.components.knx.const import DOMAIN, KNX_ADDRESS
from homeassistant.components.knx.schema import NotifySchema
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.repairs.websocket_api import (
    RepairsFlowIndexView,
    RepairsFlowResourceView,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
import homeassistant.helpers.issue_registry as ir

from .conftest import KNXTestKit

from tests.typing import ClientSessionGenerator


async def test_knx_notify_service_issue(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the legacy notify service still works before migration and repair flow is triggered."""
    await knx.setup_integration(
        {
            NotifySchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/0/0",
            }
        }
    )
    http_client = await hass_client()

    # Assert no issue is present
    assert len(issue_registry.issues) == 0

    # Simulate legacy service being used
    assert hass.services.has_service(NOTIFY_DOMAIN, NOTIFY_DOMAIN)
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        NOTIFY_DOMAIN,
        service_data={"message": "It is too cold!", "target": "test"},
        blocking=True,
    )
    await knx.assert_write(
        "1/0/0",
        (73, 116, 32, 105, 115, 32, 116, 111, 111, 32, 99, 111, 108, 100),
    )

    # Assert the issue is present
    assert len(issue_registry.issues) == 1
    assert issue_registry.async_get_issue(
        domain="notify",
        issue_id=f"migrate_notify_{DOMAIN}",
    )

    # Test confirm step in repair flow
    resp = await http_client.post(
        RepairsFlowIndexView.url,
        json={"handler": "notify", "issue_id": f"migrate_notify_{DOMAIN}"},
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    resp = await http_client.post(
        RepairsFlowResourceView.url.format(flow_id=flow_id),
    )
    assert resp.status == HTTPStatus.OK
    data = await resp.json()
    assert data["type"] == "create_entry"

    # Assert the issue is no longer present
    assert not issue_registry.async_get_issue(
        domain="notify",
        issue_id=f"migrate_notify_{DOMAIN}",
    )
    assert len(issue_registry.issues) == 0
