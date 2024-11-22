"""Tests for the seventeentrack repair flow."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.components.seventeentrack import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import goto_future, init_integration
from .conftest import DEFAULT_SUMMARY_LENGTH, get_package

from tests.common import MockConfigEntry
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator


async def test_repair(
    hass: HomeAssistant,
    mock_seventeentrack: AsyncMock,
    issue_registry: ir.IssueRegistry,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure everything starts correctly."""
    await init_integration(hass, mock_config_entry)  # 2
    assert len(hass.states.async_entity_ids()) == DEFAULT_SUMMARY_LENGTH
    assert len(issue_registry.issues) == 1

    package = get_package()
    mock_seventeentrack.return_value.profile.packages.return_value = [package]
    await goto_future(hass, freezer)

    assert hass.states.get("sensor.17track_package_friendly_name_1")
    assert len(hass.states.async_entity_ids()) == DEFAULT_SUMMARY_LENGTH + 1

    assert "deprecated" not in mock_config_entry.data

    repair_issue = issue_registry.async_get_issue(
        domain=DOMAIN, issue_id=f"deprecate_sensor_{mock_config_entry.entry_id}"
    )

    assert await async_setup_component(hass, REPAIRS_DOMAIN, {REPAIRS_DOMAIN: {}})

    client = await hass_client()

    data = await start_repair_fix_flow(client, DOMAIN, repair_issue.issue_id)

    flow_id = data["flow_id"]
    assert data == {
        "type": "form",
        "flow_id": flow_id,
        "handler": DOMAIN,
        "step_id": "confirm",
        "data_schema": [],
        "errors": None,
        "description_placeholders": None,
        "last_step": None,
        "preview": None,
    }

    data = await process_repair_fix_flow(client, flow_id)

    flow_id = data["flow_id"]
    assert data == {
        "type": "create_entry",
        "handler": DOMAIN,
        "flow_id": flow_id,
        "description": None,
        "description_placeholders": None,
    }

    assert mock_config_entry.data["deprecated"]

    repair_issue = issue_registry.async_get_issue(
        domain=DOMAIN, issue_id="deprecate_sensor"
    )

    assert repair_issue is None

    await goto_future(hass, freezer)
    assert len(hass.states.async_entity_ids()) == DEFAULT_SUMMARY_LENGTH
