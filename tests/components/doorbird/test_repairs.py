"""Test repairs for doorbird."""

from __future__ import annotations

from http import HTTPStatus

from homeassistant.components.doorbird.const import DOMAIN
from homeassistant.components.repairs.issue_handler import (
    async_process_repairs_platforms,
)
from homeassistant.components.repairs.websocket_api import (
    RepairsFlowIndexView,
    RepairsFlowResourceView,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import mock_not_found_exception
from .conftest import DoorbirdMockerType

from tests.typing import ClientSessionGenerator


async def test_change_schedule_fails(
    hass: HomeAssistant,
    doorbird_mocker: DoorbirdMockerType,
    hass_client: ClientSessionGenerator,
) -> None:
    """Test a doorbird when change_schedule fails."""
    assert await async_setup_component(hass, "repairs", {})
    doorbird_entry = await doorbird_mocker(
        favorites_side_effect=mock_not_found_exception()
    )
    assert doorbird_entry.entry.state is ConfigEntryState.SETUP_RETRY
    issue_reg = ir.async_get(hass)
    assert len(issue_reg.issues) == 1
    issue = list(issue_reg.issues.values())[0]
    issue_id = issue.issue_id
    assert issue.domain == DOMAIN

    await async_process_repairs_platforms(hass)
    client = await hass_client()

    url = RepairsFlowIndexView.url
    resp = await client.post(url, json={"handler": DOMAIN, "issue_id": issue_id})
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    flow_id = data["flow_id"]
    placeholders = data["description_placeholders"]
    assert "404" in placeholders["error"]
    assert data["step_id"] == "confirm"

    url = RepairsFlowResourceView.url.format(flow_id=flow_id)
    resp = await client.post(url)
    assert resp.status == HTTPStatus.OK
    data = await resp.json()

    assert data["type"] == "create_entry"
