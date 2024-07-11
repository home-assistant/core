"""Test repairs for Ecobee integration."""

from http import HTTPStatus
from unittest.mock import MagicMock

from homeassistant.components.climate import (
    ATTR_AUX_HEAT,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_AUX_HEAT,
)
from homeassistant.components.ecobee import DOMAIN
from homeassistant.components.notify import DOMAIN as NOTIFY_DOMAIN
from homeassistant.components.repairs.issue_handler import (
    async_process_repairs_platforms,
)
from homeassistant.components.repairs.websocket_api import (
    RepairsFlowIndexView,
    RepairsFlowResourceView,
)
from homeassistant.const import ATTR_ENTITY_ID
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

    url = RepairsFlowIndexView.url
    resp = await http_client.post(
        url, json={"handler": "notify", "issue_id": f"migrate_notify_{DOMAIN}_{DOMAIN}"}
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
        domain="notify",
        issue_id=f"migrate_notify_{DOMAIN}_{DOMAIN}",
    )
    assert len(issue_registry.issues) == 0


async def test_ecobee_aux_heat_repair_flow(
    hass: HomeAssistant,
    mock_ecobee: MagicMock,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test the ecobee aux_heat service repair flow is triggered."""
    await setup_platform(hass, CLIMATE_DOMAIN)
    await async_process_repairs_platforms(hass)

    ENTITY_ID = "climate.ecobee2"

    # Simulate legacy service being used
    assert hass.services.has_service(CLIMATE_DOMAIN, SERVICE_SET_AUX_HEAT)
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_AUX_HEAT,
        {ATTR_ENTITY_ID: ENTITY_ID, ATTR_AUX_HEAT: True},
        blocking=True,
    )

    # Assert the issue is present
    assert issue_registry.async_get_issue(
        domain="ecobee",
        issue_id="migrate_aux_heat",
    )
    assert len(issue_registry.issues) == 1
