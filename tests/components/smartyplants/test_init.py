"""Tests for the SmartyPlants integration setup."""

from unittest.mock import AsyncMock

from pysmartyplants import (
    SmartyPlantsAuthError,
    SmartyPlantsConnectionError,
    SmartyPlantsError,
)
import pytest

from homeassistant.components.smartyplants.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_WEBHOOK_ID
from homeassistant.core import HomeAssistant

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_load_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the entry loads and unloads."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(SmartyPlantsConnectionError("boom"), id="connection"),
        pytest.param(SmartyPlantsAuthError("nope"), id="auth"),
    ],
)
async def test_setup_retries_when_first_poll_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_smartyplants_client: AsyncMock,
    error: SmartyPlantsError,
) -> None:
    """Test setup is retried when the first poll fails."""
    mock_smartyplants_client.async_get_sensors.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.usefixtures("mock_smartyplants_client")
async def test_entry_without_webhook_polls(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test an entry created without a webhook still loads and polls."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            key: value
            for key, value in mock_config_entry.data.items()
            if key != CONF_WEBHOOK_ID
        },
        unique_id=mock_config_entry.unique_id,
    )
    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    assert hass.states.get("sensor.monstera_temperature").state == "22.5"
