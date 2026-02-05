"""Test Hikvision integration setup and unload."""

from unittest.mock import MagicMock
from xml.etree.ElementTree import ParseError

import pytest
import requests

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_SSL
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

    # Verify HikCamera was called with the ssl parameter
    mock_hikcamera.assert_called_once_with(
        f"http://{TEST_HOST}", TEST_PORT, TEST_USERNAME, TEST_PASSWORD, False
    )

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_hikcamera.return_value.disconnect.assert_called_once()


async def test_setup_entry_with_ssl(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test setup with ssl enabled passes ssl parameter to HikCamera."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_SSL: True}
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify HikCamera was called with ssl=True
    mock_hikcamera.assert_called_once_with(
        f"https://{TEST_HOST}", TEST_PORT, TEST_USERNAME, TEST_PASSWORD, True
    )


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
    mock_hikcamera.return_value.get_id = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_nvr_fetches_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
) -> None:
    """Test setup fetches NVR events for NVR devices."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.get_event_triggers.assert_called_once()
    mock_hik_nvr.return_value.inject_events.assert_called_once()


async def test_setup_entry_nvr_event_fetch_request_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup continues when NVR event fetch fails with request error."""
    mock_hik_nvr.return_value.get_event_triggers.side_effect = (
        requests.exceptions.RequestException("Connection error")
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.get_event_triggers.assert_called_once()
    mock_hik_nvr.return_value.inject_events.assert_not_called()
    assert f"Unable to fetch event triggers from {TEST_HOST}" in caplog.text


async def test_setup_entry_nvr_event_fetch_parse_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup continues when NVR event fetch fails with parse error."""
    mock_hik_nvr.return_value.get_event_triggers.side_effect = ParseError("Invalid XML")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.get_event_triggers.assert_called_once()
    mock_hik_nvr.return_value.inject_events.assert_not_called()
    assert f"Unable to fetch event triggers from {TEST_HOST}" in caplog.text


async def test_setup_entry_nvr_no_events_returned(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
) -> None:
    """Test setup continues when NVR returns no events."""
    mock_hik_nvr.return_value.get_event_triggers.return_value = None

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.get_event_triggers.assert_called_once()
    mock_hik_nvr.return_value.inject_events.assert_not_called()


async def test_setup_entry_nvr_empty_events_returned(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
) -> None:
    """Test setup continues when NVR returns empty events."""
    mock_hik_nvr.return_value.get_event_triggers.return_value = {}

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.get_event_triggers.assert_called_once()
    mock_hik_nvr.return_value.inject_events.assert_not_called()
