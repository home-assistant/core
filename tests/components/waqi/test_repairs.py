"""Test the World Air Quality Index (WAQI) repairs."""

from unittest.mock import AsyncMock

from aiowaqi import WAQIUnknownStationError

from homeassistant.components.repairs import DOMAIN as REPAIRS_DOMAIN
from homeassistant.components.waqi.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import setup_integration

from tests.common import MockConfigEntry
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator


async def test_station_not_found_fix_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the station not found fix flow removes the subentry."""
    assert await async_setup_component(hass, REPAIRS_DOMAIN, {REPAIRS_DOMAIN: {}})

    subentry_id = list(mock_config_entry.subentries)[0]
    mock_waqi.get_by_station_number.side_effect = WAQIUnknownStationError(
        "Could not find station @4585"
    )
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    issue_id = f"station_not_found_{subentry_id}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_key == "station_not_found"
    assert issue.is_fixable is True
    assert issue.data == {
        "entry_id": mock_config_entry.entry_id,
        "subentry_id": subentry_id,
        "name": "de Jongweg, Utrecht",
    }

    http_client = await hass_client()

    data = await start_repair_fix_flow(http_client, DOMAIN, issue_id)
    flow_id = data["flow_id"]

    assert data["step_id"] == "confirm"
    assert data["description_placeholders"] == {"name": "de Jongweg, Utrecht"}

    data = await process_repair_fix_flow(http_client, flow_id, json={})

    assert data["type"] == "create_entry"

    await hass.async_block_till_done()

    assert subentry_id not in mock_config_entry.subentries
    assert not issue_registry.async_get_issue(DOMAIN, issue_id)


async def test_issue_cleared_on_recovery(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_waqi: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the issue is removed once the station is reachable again."""
    subentry_id = list(mock_config_entry.subentries)[0]
    mock_waqi.get_by_station_number.side_effect = WAQIUnknownStationError(
        "Could not find station @4585"
    )
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY

    issue_id = f"station_not_found_{subentry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is not None

    mock_waqi.get_by_station_number.side_effect = None
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
