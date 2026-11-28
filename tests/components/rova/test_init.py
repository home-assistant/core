"""Tests for the Rova integration init."""

from unittest.mock import MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry
from requests import ConnectTimeout
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.rova.const import (
    CONF_HOUSE_NUMBER,
    CONF_HOUSE_NUMBER_SUFFIX,
    CONF_ZIP_CODE,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from . import setup_with_selected_platforms


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

    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.unique_id), mock_config_entry.entry_id
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
    issue_id = f"no_rova_area_{mock_config_entry.entry_id}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.config_entry_id == mock_config_entry.entry_id
    assert issue.translation_placeholders == {"address": "8381BE 13"}

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_issue_if_not_rova_area_same_zip_code(
    hass: HomeAssistant,
    mock_rova: MagicMock,
    mock_config_entry: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test each address in the same zip code gets its own issue."""
    mock_rova.is_rova_area.return_value = False
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="8381BE13A",
        title="8381BE 13 A",
        data={
            CONF_ZIP_CODE: "8381BE",
            CONF_HOUSE_NUMBER: "13",
            CONF_HOUSE_NUMBER_SUFFIX: "A",
        },
    )
    mock_config_entry.add_to_hass(hass)
    other_entry.add_to_hass(hass)
    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(issue_registry.issues) == 2
    for entry, address in (
        (mock_config_entry, "8381BE 13"),
        (other_entry, "8381BE 13 A"),
    ):
        assert entry.state is ConfigEntryState.SETUP_ERROR
        issue = issue_registry.async_get_issue(DOMAIN, f"no_rova_area_{entry.entry_id}")
        assert issue is not None
        assert issue.config_entry_id == entry.entry_id
        assert issue.translation_placeholders == {"address": address}

    await hass.config_entries.async_remove(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(issue_registry.issues) == 1
    assert issue_registry.async_get_issue(
        DOMAIN, f"no_rova_area_{other_entry.entry_id}"
    )
