"""Test repairs for KNX integration."""

from http import HTTPStatus

from homeassistant.components.knx.const import DOMAIN, KNX_ADDRESS
from homeassistant.components.knx.schema import NotifySchema
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.components.repairs.issue_handler import (
    async_process_repairs_platforms,
)
from homeassistant.components.repairs.websocket_api import (
    RepairsFlowIndexView,
    RepairsFlowResourceView,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import KNXTestKit

from tests.typing import ClientSessionGenerator, WebSocketGenerator


async def test_knx_notify_service_issue(
    hass: HomeAssistant,
    knx: KNXTestKit,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the legacy notify service still works before migration and repair flow is triggered."""
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {REPAIRS_DOMAIN: {}})
    await knx.setup_integration(
        {
            NotifySchema.PLATFORM: {
                CONF_NAME: "test",
                KNX_ADDRESS: "1/0/0",
            }
        }
    )

    await async_process_repairs_platforms(hass)

    ws_client = await hass_ws_client(hass)
    http_client = await hass_client()

    # Assert no issue is present
    await ws_client.send_json_auto_id({"type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 0

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
    await ws_client.send_json_auto_id({"type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
    issue = msg["result"]["issues"][0]
    assert issue["issue_id"] == "migrate_notify"

    url = RepairsFlowIndexView.url
    resp = await http_client.post(
        url, json={"handler": DOMAIN, "issue_id": "migrate_notify"}
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
    await ws_client.send_json_auto_id({"type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 0
