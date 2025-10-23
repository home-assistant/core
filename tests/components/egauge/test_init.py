"""Tests for the eGauge integration."""

from unittest.mock import MagicMock

from egauge_async.json.client import EgaugeAuthenticationError
from httpx import ConnectError
import pytest

from homeassistant.components.egauge import _build_client_url
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


async def test_setup_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
) -> None:
    """Test setup with connection error."""
    mock_config_entry.add_to_hass(hass)
    mock_egauge_client.get_device_serial_number.side_effect = ConnectError

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_auth_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_egauge_client: MagicMock,
) -> None:
    """Test setup with authentication error."""
    mock_config_entry.add_to_hass(hass)
    mock_egauge_client.get_device_serial_number.side_effect = EgaugeAuthenticationError

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR


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


@pytest.mark.parametrize(
    ("host", "use_ssl", "expected"),
    [
        ("egauge.local", True, "https://egauge.local"),
        ("egauge.local", False, "http://egauge.local"),
        ("192.168.1.1", True, "https://192.168.1.1"),
        ("192.168.1.1", False, "http://192.168.1.1"),
    ],
)
def test_build_client_url(host: str, use_ssl: bool, expected: str) -> None:
    """Test building a URL for the eGauge client."""
    assert _build_client_url(host, use_ssl) == expected
