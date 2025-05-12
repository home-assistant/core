"""Tests for the IRM KMI integration."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant.components.irm_kmi.const import CONF_LANGUAGE_OVERRIDE, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ZONE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_irm_kmi_api: AsyncMock,
) -> None:
    """Test the IRM KMI configuration entry loading/unloading."""
    mock_config_entry.runtime_data.api_client = mock_irm_kmi_api

    hass.states.async_set(
        "zone.home",
        0,
        {"latitude": 50.738, "longitude": 4.054},
    )

    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_exception_irm_kmi_api: AsyncMock,
) -> None:
    """Test the IRM KMI configuration entry not ready."""
    hass.states.async_set(
        "zone.home",
        0,
        {"latitude": 50.738681639, "longitude": 4.054077148},
    )

    mock_config_entry.runtime_data.api_client = mock_exception_irm_kmi_api
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_exception_irm_kmi_api.refresh_forecasts_coord.call_count == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_zone_removed(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the IRM KMI configuration entry not ready."""
    mock_config_entry = MockConfigEntry(
        title="My Castle",
        domain=DOMAIN,
        data={CONF_ZONE: "zone.castle", CONF_LANGUAGE_OVERRIDE: "none"},
        unique_id="zone.castle",
    )
    mock_config_entry.runtime_data = MagicMock()
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert "Zone 'zone.castle' not found" in caplog.text
