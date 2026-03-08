"""Tests for the eGauge integration."""

from unittest.mock import MagicMock

from egauge_async.exceptions import (
    EgaugeAuthenticationError,
    EgaugeParsingException,
    EgaugePermissionError,
)
from httpx import ConnectError
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_setup_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
) -> None:
    """Test successful setup."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_egauge_client.get_device_serial_number.called
    assert mock_egauge_client.get_hostname.called
    assert mock_egauge_client.get_register_info.called


@pytest.mark.parametrize(
    ("exception", "expected"),
    [
        (ConnectError, ConfigEntryState.SETUP_RETRY),
        (EgaugeAuthenticationError, ConfigEntryState.SETUP_ERROR),
        (EgaugePermissionError, ConfigEntryState.SETUP_ERROR),
        (EgaugeParsingException, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
    exception: Exception,
    expected: ConfigEntryState,
) -> None:
    """Test setup with connection error."""
    mock_config_entry.add_to_hass(hass)
    mock_egauge_client.get_device_serial_number.side_effect = exception

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is expected


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
