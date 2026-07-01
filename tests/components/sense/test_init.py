"""Tests for the Sense integration setup."""

import socket
from unittest.mock import MagicMock

import pytest
from sense_energy import (
    SenseAPIException,
    SenseAPITimeoutException,
    SenseAuthenticationException,
    SenseMFARequiredException,
    SenseWebsocketException,
)

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    "exception",
    [
        SenseAPITimeoutException(),
        SenseWebsocketException(),
    ],
)
async def test_setup_entry_exceptions(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test we handle exceptions during async_setup_entry and can recover."""
    mock_sense.update_realtime.side_effect = exception
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY

    # Verify recovery: clear the error and reload the entry
    mock_sense.update_realtime.side_effect = None
    assert await hass.config_entries.async_reload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.parametrize(
    "exception",
    [
        SenseAuthenticationException(),
        SenseMFARequiredException(),
    ],
)
async def test_setup_get_monitor_data_auth_exceptions(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test auth exceptions from get_monitor_data result in a failed entry."""
    mock_sense.get_monitor_data.side_effect = exception
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR


@pytest.mark.parametrize(
    "exception",
    [
        SenseAPITimeoutException(),
        TimeoutError(),
        SenseAPIException("connect error"),
        socket.gaierror(),
    ],
)
async def test_setup_get_monitor_data_retry_exceptions(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test timeout and connect exceptions from get_monitor_data result in a retryable entry."""
    mock_sense.get_monitor_data.side_effect = exception
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "exception",
    [
        SenseAPITimeoutException(),
        TimeoutError(),
        SenseAPIException("connect error"),
        socket.gaierror(),
        SenseWebsocketException("ws error"),
        SenseAPIException(),
    ],
)
async def test_setup_get_realtime_retry_exceptions(
    hass: HomeAssistant,
    mock_sense: MagicMock,
    config_entry: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test timeout and connect exceptions from update_realtime result in a retryable entry."""
    mock_sense.update_realtime.side_effect = exception
    config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_RETRY
