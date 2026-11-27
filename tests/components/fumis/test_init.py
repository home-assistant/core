"""Tests for the Fumis integration."""

import logging
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from fumis import (
    FumisAuthenticationError,
    FumisConnectionError,
    FumisError,
    FumisStoveOfflineError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.fumis.const import DOMAIN, SCAN_INTERVAL
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("mock_fumis")
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("side_effect", "expected_log"),
    [
        (FumisConnectionError, "communicating with the Fumis online service"),
        (FumisStoveOfflineError, "not connected to the internet"),
        (FumisError, "communicating with the Fumis online service"),
    ],
)
async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    side_effect: type[Exception],
    expected_log: str,
) -> None:
    """Test the config entry not ready."""
    mock_fumis.update_info.side_effect = side_effect

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert expected_log in caplog.text


async def test_config_entry_authentication_failed(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the config entry authentication error triggers reauth."""
    mock_fumis.update_info.side_effect = FumisAuthenticationError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN
    assert flow["context"].get("source") == SOURCE_REAUTH
    assert flow["context"].get("entry_id") == mock_config_entry.entry_id


@pytest.mark.parametrize(
    ("side_effect", "level"),
    [
        pytest.param(FumisStoveOfflineError, logging.INFO, id="stove_offline"),
        pytest.param(FumisConnectionError, logging.ERROR, id="connection_error"),
        pytest.param(FumisError, logging.ERROR, id="unknown_error"),
    ],
)
@pytest.mark.usefixtures("init_integration")
async def test_refresh_log_level(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
    side_effect: type[Exception],
    level: int,
) -> None:
    """Test an offline stove is logged at info level."""
    mock_fumis.update_info.side_effect = side_effect

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert [
        record.levelno
        for record in caplog.records
        if record.name == "homeassistant.components.fumis"
        and record.levelno > logging.DEBUG
    ] == [level]
