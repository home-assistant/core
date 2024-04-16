"""Test repairs for Ecobee integration."""

from http import HTTPStatus
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.ecobee import (
    DATA_FLOW_MINOR_VERSION,
    DATA_FLOW_VERSION,
    DOMAIN,
)
from homeassistant.components.notify import (
    DOMAIN as NOTIFY_DOMAIN,
    SERVICE_SEND_MESSAGE,
)
from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.components.repairs.issue_handler import (
    async_process_repairs_platforms,
)
from homeassistant.components.repairs.websocket_api import (
    RepairsFlowIndexView,
    RepairsFlowResourceView,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .common import setup_platform

from tests.typing import ClientSessionGenerator, WebSocketGenerator

THERMOSTAT_ID = 0


async def test_ecobee_notify_fix_flow(
    hass: HomeAssistant, mock_ecobee: MagicMock
) -> None:
    """Test the legacy notify service still works before migration and issue flow is triggered."""
    with patch(
        "homeassistant.components.ecobee.ir.async_create_issue"
    ) as mock_async_create_issue:
        await setup_platform(hass, NOTIFY_DOMAIN, version=1, minor_version=1)
        mock_async_create_issue.assert_called()

    # Test legacy service
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

    # Test entity service
    entity_id = "notify.ecobee"
    state = hass.states.get("notify.ecobee")
    assert state is not None
    assert hass.services.has_service(NOTIFY_DOMAIN, SERVICE_SEND_MESSAGE)
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        service_data={"entity_id": entity_id, "message": "It is too cold!"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_ecobee.send_message.assert_called_with(THERMOSTAT_ID, "It is too cold!")


@pytest.mark.parametrize(
    ("next_step_id", "response_type", "reason", "version"),
    [
        ("confirm", "create_entry", None, (DATA_FLOW_VERSION, DATA_FLOW_MINOR_VERSION)),
        ("ignore", "abort", "issue_ignored", (1, 1)),
    ],
    ids=["fix", "ignore"],
)
async def test_ecobee_repair_flow(
    hass: HomeAssistant,
    mock_ecobee: MagicMock,
    hass_client: ClientSessionGenerator,
    hass_ws_client: WebSocketGenerator,
    next_step_id: str,
    response_type: str,
    reason: str | None,
    version: tuple[int, int],
) -> None:
    """Test the legacy notify service still works before migration and repair flow is triggered."""
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {REPAIRS_DOMAIN: {}})
    entry = await setup_platform(hass, NOTIFY_DOMAIN, version=1, minor_version=1)
    await async_process_repairs_platforms(hass)

    ws_client = await hass_ws_client(hass)
    http_client = await hass_client()

    # Assert the issue is present
    await ws_client.send_json({"id": 1, "type": "repairs/list_issues"})
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
    assert data["step_id"] == "init"

    url = RepairsFlowResourceView.url.format(flow_id=flow_id)

    # Show menu
    resp = await http_client.post(url)

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["type"] == "menu"

    # Test menu step in repair flow
    resp = await http_client.post(url, json={"next_step_id": next_step_id})

    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["type"] == response_type
    assert data.get("reason") == reason

    await hass.async_block_till_done()
    assert entry.version == version[0]
    assert entry.minor_version == version[1]


async def test_ecobee_notify_migrated(
    hass: HomeAssistant, mock_ecobee: MagicMock
) -> None:
    """Test the legacy notify service still works before migration and repair flow is triggered."""
    await setup_platform(
        hass,
        NOTIFY_DOMAIN,
        version=DATA_FLOW_VERSION,
        minor_version=DATA_FLOW_MINOR_VERSION,
    )

    # Test legacy service
    assert not hass.services.has_service(NOTIFY_DOMAIN, DOMAIN)

    # Test entity service
    entity_id = "notify.ecobee"
    state = hass.states.get("notify.ecobee")
    assert state is not None
    assert hass.services.has_service(NOTIFY_DOMAIN, SERVICE_SEND_MESSAGE)
    await hass.services.async_call(
        NOTIFY_DOMAIN,
        SERVICE_SEND_MESSAGE,
        service_data={"entity_id": entity_id, "message": "It is too cold!"},
        blocking=True,
    )
    await hass.async_block_till_done()
    mock_ecobee.send_message.assert_called_with(THERMOSTAT_ID, "It is too cold!")
