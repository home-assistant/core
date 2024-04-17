"""Test repairs for KNX integration."""

from homeassistant.components.knx.const import KNX_ADDRESS
from homeassistant.components.knx.schema import NotifySchema
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.components.repairs.issue_handler import (
    async_process_repairs_platforms,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import KNXTestKit

from tests.typing import WebSocketGenerator


async def test_knx_notify_service_issue(
    hass: HomeAssistant,
    knx: KNXTestKit,
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

    # Assert no issue is present
    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
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
    await ws_client.send_json({"id": 2, "type": "repairs/list_issues"})
    msg = await ws_client.receive_json()
    assert msg["success"]
    assert len(msg["result"]["issues"]) == 1
