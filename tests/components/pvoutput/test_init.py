"""Tests for the PVOutput integration."""
from unittest.mock import MagicMock

from pvo import (
    PVOutputAuthenticationError,
    PVOutputConnectionError,
    PVOutputNoDataError,
)
import pytest

from homeassistant.components.pvoutput.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pvoutput: MagicMock,
) -> None:
    """Test the PVOutput configuration entry loading/unloading."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(mock_pvoutput.status.mock_calls) == 1
    assert len(mock_pvoutput.system.mock_calls) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not hass.data.get(DOMAIN)
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize("side_effect", [PVOutputConnectionError, PVOutputNoDataError])
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pvoutput: MagicMock,
    side_effect: Exception,
) -> None:
    """Test the PVOutput configuration entry not ready."""
    mock_pvoutput.status.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert len(mock_pvoutput.status.mock_calls) == 1
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_config_entry_authentication_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pvoutput: MagicMock,
) -> None:
    """Test trigger reauthentication flow."""
    mock_config_entry.add_to_hass(hass)

    mock_pvoutput.status.side_effect = PVOutputAuthenticationError

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow.get("step_id") == "reauth_confirm"
    assert flow.get("handler") == DOMAIN

    assert "context" in flow
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id
