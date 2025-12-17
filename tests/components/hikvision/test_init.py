"""Test Hikvision integration setup and unload."""

from unittest.mock import MagicMock

import pytest
import requests

from homeassistant.components.hikvision.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant

from . import setup_integration
from .conftest import TEST_HOST, TEST_PASSWORD, TEST_PORT, TEST_USERNAME

from tests.common import MockConfigEntry


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test successful setup and unload of config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hikcamera.return_value.start_stream.assert_called_once()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_hikcamera.return_value.disconnect.assert_called_once()


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test setup fails on connection error."""
    mock_hikcamera.side_effect = requests.exceptions.RequestException(
        "Connection failed"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_no_device_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test setup fails when device_id is None."""
    mock_hikcamera.return_value.get_id.return_value = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("ssl", [False, True])
async def test_setup_entry_passes_ssl_parameter(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    ssl: bool,
) -> None:
    """Test that ssl parameter is passed to HikCamera."""
    mock_config_entry = MockConfigEntry(
        title="Test Camera",
        domain=DOMAIN,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: TEST_PORT,
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
            CONF_SSL: ssl,
        },
        unique_id="test_device_id",
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify HikCamera was called with the ssl parameter
    expected_url = f"{'https' if ssl else 'http'}://{TEST_HOST}"
    mock_hikcamera.assert_called_once_with(
        expected_url, TEST_PORT, TEST_USERNAME, TEST_PASSWORD, ssl
    )
