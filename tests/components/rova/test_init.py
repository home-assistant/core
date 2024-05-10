"""Tests for the Rova integration init."""

from unittest.mock import MagicMock

import pytest
from requests import ConnectTimeout
from syrupy import SnapshotAssertion

from homeassistant.components.rova import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from tests.common import MockConfigEntry
from tests.components.rova import setup_with_selected_platforms


async def test_reload(
    hass: HomeAssistant,
    mock_rova: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reloading the integration."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_service(
    hass: HomeAssistant,
    mock_rova: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Rova service."""
    await setup_with_selected_platforms(hass, mock_config_entry, [Platform.SENSOR])

    device_entry = device_registry.async_get_device(
        identifiers={(DOMAIN, mock_config_entry.unique_id)}
    )
    assert device_entry is not None
    assert device_entry == snapshot


@pytest.mark.parametrize(
    "method",
    [
        "is_rova_area",
        "get_calendar_items",
    ],
)
async def test_retry_after_failure(
    hass: HomeAssistant,
    mock_rova: MagicMock,
    mock_config_entry: MockConfigEntry,
    method: str,
) -> None:
    """Test we retry after a failure."""
    getattr(mock_rova, method).side_effect = ConnectTimeout
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_issue_if_not_rova_area(
    hass: HomeAssistant,
    mock_rova: MagicMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test we create an issue if rova does not collect at the given address."""
    mock_rova.is_rova_area.return_value = False
    mock_config_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert len(issue_registry.issues) == 1
