"""Tests for QNAP update platform."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_firmware_update_no_update(
    hass: HomeAssistant,
    mock_qnap_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Update entity state is OFF when get_firmware_update() returns None."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("update.test_nas_firmware_update")
    assert state is not None
    assert state.state == STATE_OFF
    assert state == snapshot


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_firmware_update_available(
    hass: HomeAssistant,
    mock_qnap_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Update entity state is ON when a newer firmware version is available."""
    mock_qnap_client.get_firmware_update.return_value = "5.2.0.1234 Build 20240101"

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("update.test_nas_firmware_update")
    assert state is not None
    assert state.state == STATE_ON
    assert state == snapshot


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_firmware_update_error_state(
    hass: HomeAssistant,
    mock_qnap_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Update entity returns None (no update shown) when firmware API returns 'error'."""
    mock_qnap_client.get_firmware_update.return_value = "error"

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("update.test_nas_firmware_update")
    assert state is not None
    # When latest_version returns None, HA treats entity as up-to-date (OFF)
    assert state.state == STATE_OFF


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_firmware_installed_version(
    hass: HomeAssistant,
    mock_qnap_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """installed_version reflects the firmware version from system_stats."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("update.test_nas_firmware_update")
    assert state is not None
    assert state.attributes["installed_version"] == "5.1.0.2548"
