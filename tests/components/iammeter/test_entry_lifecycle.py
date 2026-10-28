"""Regression coverage for config-entry ownership and failed setup."""

from unittest.mock import MagicMock

from iammeter.async_client import IammeterConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.iammeter.const import DOMAIN
from homeassistant.components.iammeter.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.config_entries import ConfigEntryDisabler, ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir
from homeassistant.setup import async_setup_component

from . import MOCK_DATA, MOCK_INPUT


@pytest.mark.parametrize(
    "unique_id", ["test-meter-3-2", "test-meter_Power_NET", "test-meter_Power_Net"]
)
async def test_import_missing_net(
    hass: HomeAssistant,
    mock_meter: MagicMock,
    entity_registry: er.EntityRegistry,
    unique_id: str,
) -> None:
    """Adopt historical NET entities even when the meter no longer reports NET."""
    old = entity_registry.async_get_or_create(
        Platform.SENSOR, DOMAIN, unique_id, suggested_object_id="original_net"
    )
    unrelated = entity_registry.async_get_or_create(
        Platform.SENSOR, DOMAIN, "other-meter_Power_Net"
    )
    mock_meter.return_value.async_get_data.return_value = {
        "Model": "WEM3080T",
        "sn": "test-meter",
        "Power_A": 460,
    }
    assert await async_setup_component(
        hass, "sensor", {"sensor": {"platform": DOMAIN, **MOCK_INPUT}}
    )
    await hass.async_block_till_done()
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    migrated = entity_registry.async_get(old.entity_id)
    assert migrated.unique_id == "test-meter_Power_Net"
    assert migrated.config_entry_id == entry.entry_id
    assert migrated.device_id is not None
    assert hass.states.get(old.entity_id).state == STATE_UNAVAILABLE
    assert entity_registry.async_get(unrelated.entity_id).config_entry_id is None


async def test_diagnostics_after_failed_setup(
    hass: HomeAssistant, mock_meter: MagicMock, mock_entry: MockConfigEntry
) -> None:
    """Connection failures must not prevent downloading redacted diagnostics."""
    mock_meter.return_value.async_get_data.side_effect = IammeterConnectionError()
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_entry.state is ConfigEntryState.SETUP_RETRY
    data = await async_get_config_entry_diagnostics(hass, mock_entry)
    assert data["entry"]["data"]["host"] == "**REDACTED**"
    assert "measurement" not in data
    assert "last_update_success" not in data


async def test_diagnostics_after_unload(
    hass: HomeAssistant, mock_meter: MagicMock, mock_entry: MockConfigEntry
) -> None:
    """Unloaded entries still provide redacted configuration diagnostics."""
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    await hass.config_entries.async_unload(mock_entry.entry_id)
    data = await async_get_config_entry_diagnostics(hass, mock_entry)
    assert data["entry"]["unique_id"] == "**REDACTED**"
    assert "measurement" not in data


async def test_identity_issue_lifecycle(
    hass: HomeAssistant,
    mock_meter: MagicMock,
    mock_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Hide identity warnings on disable and remove them with the meter entry."""
    mock_meter.return_value.async_get_data.return_value = {
        **MOCK_DATA,
        "sn": "replacement",
    }
    mock_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()
    issue_id = f"identity_changed_{mock_entry.entry_id}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue.config_entry_id == mock_entry.entry_id
    await hass.config_entries.async_set_disabled_by(
        mock_entry.entry_id, ConfigEntryDisabler.USER
    )
    await hass.async_block_till_done()
    assert issue_registry.async_is_hidden(issue)
    await hass.config_entries.async_remove(mock_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
