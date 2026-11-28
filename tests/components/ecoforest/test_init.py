"""Tests for the Ecoforest integration setup."""

from unittest.mock import Mock, patch

from freezegun.api import FrozenDateTimeFactory
from pyecoforest.exceptions import (
    EcoforestAuthenticationRequired,
    EcoforestConnectionError,
)
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.ecoforest.const import POLLING_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_authentication_failed(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setup starts a reauth flow when authentication on the device fails."""
    with patch(
        "pyecoforest.api.EcoforestApi.get",
        side_effect=EcoforestAuthenticationRequired("401"),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    assert config_entry.reason == "Authentication on device 1.1.1.1 failed"

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == config_entry.entry_id


async def test_setup_connection_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test setup retries when the device cannot be reached."""
    with patch(
        "pyecoforest.api.EcoforestApi.get",
        side_effect=EcoforestConnectionError,
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()


async def test_update_authentication_failed(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    config_entry: MockConfigEntry,
    mock_device: Mock,
) -> None:
    """Test an authentication error during an update starts a reauth flow."""
    with patch(
        "pyecoforest.api.EcoforestApi.get", return_value=mock_device
    ) as mock_get:
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        mock_get.side_effect = EcoforestAuthenticationRequired("401")
        freezer.tick(POLLING_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == config_entry.entry_id
