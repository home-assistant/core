"""Tests for the WLED integration."""

import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from wled import WLEDConnectionError

from homeassistant.components.wled.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir

from tests.common import MockConfigEntry


@pytest.mark.parametrize("device_fixture", ["rgb_websocket"])
async def test_load_unload_config_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_wled: AsyncMock
) -> None:
    """Test the WLED configuration entry unloading."""
    connection_connected = asyncio.Future()
    connection_finished = asyncio.Future()

    async def connect(callback: Callable):
        connection_connected.set_result(None)
        await connection_finished

    # Mock out wled.listen with a Future
    mock_wled.listen.side_effect = connect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await connection_connected

    # Ensure config entry is loaded and are connected
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_wled.connect.call_count == 1
    assert mock_wled.disconnect.call_count == 0

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure everything is cleaned up nicely and are disconnected
    assert mock_wled.disconnect.call_count == 1


@patch(
    "homeassistant.components.wled.coordinator.WLED.request",
    side_effect=WLEDConnectionError,
)
async def test_config_entry_not_ready(
    mock_request: MagicMock, hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the WLED configuration entry not ready."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_request.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setting_unique_id(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test we set unique ID if not set yet."""
    assert init_integration.runtime_data
    assert init_integration.unique_id == "aabbccddeeff"


@pytest.mark.parametrize(
    (
        "duplicated_entries_count",
        "translation_key",
    ),
    [
        (2, "config_entry_unique_id_collision"),
        (6, "config_entry_unique_id_collision_many"),
    ],
)
async def test_handle_device_conflict_creates_issue_for_duplicates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
    duplicated_entries_count: int,
    translation_key: str,
) -> None:
    """When there are multiple entries for the same MAC, create an issue."""
    mock_config_entry.add_to_hass(hass)
    assert mock_config_entry.unique_id

    duplicated_entries = []
    for i in range(1, duplicated_entries_count):
        new_entry = MockConfigEntry(
            domain=DOMAIN,
            title=f"Duplicate WLED #{i}",
            unique_id=mock_config_entry.unique_id.upper(),
            data=mock_config_entry.data,
        )
        new_entry.add_to_hass(hass)
        duplicated_entries.append(new_entry)

    issue_reg = ir.async_get(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    issue_id = f"device_conflict_{mock_config_entry.entry_id}"
    assert (issue := issue_reg.async_get_issue(DOMAIN, issue_id))

    assert issue.domain == DOMAIN
    assert issue.is_fixable is False
    assert issue.severity == ir.IssueSeverity.WARNING
    assert issue.translation_key == translation_key

    # Check translation placeholders
    assert (placeholders := issue.translation_placeholders)
    assert placeholders["configure_url"] == "/config/integrations/integration/wled"
    assert placeholders["unique_id"] == mock_config_entry.unique_id

    # Two titles should be listed in "titles"
    titles = placeholders["titles"]
    assert "'Main WLED'" in titles
    assert "`Duplicate WLED #1`" in titles

    # When there is a conflict, we do not change the unique_id
    assert mock_config_entry.unique_id == "aabbccddeeff"
    assert duplicated_entries[0].unique_id == "AABBCCDDEEFF"


async def test_handle_device_conflict_normalizes_unique_id_without_duplicates(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """When only one entry exists, normalize MAC and delete any existing issue."""
    assert mock_config_entry.unique_id

    mock_config_entry.add_to_hass(hass)

    # Create a dummy issue to be removed
    issue_id = f"device_conflict_{mock_config_entry.entry_id}"
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key="config_entry_unique_id_collision",
        translation_placeholders={
            "configure_url": f"/config/integrations/integration/{DOMAIN}",
            "unique_id": mock_config_entry.unique_id,
            "titles": "'Main WLED', 'Duplicate WLED'",
        },
        data={},
    )

    issue_reg = ir.async_get(hass)

    assert issue_reg.async_get_issue(DOMAIN, issue_id)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Issue should be removed
    assert issue_id not in issue_reg.issues

    # Unique_id should be normalized
    assert mock_config_entry.unique_id == "aabbccddeeff"
