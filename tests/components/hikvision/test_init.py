"""Test Hikvision integration setup and unload."""

import logging
from unittest.mock import MagicMock
from xml.etree.ElementTree import ParseError

import pytest
from pytest_homeassistant.common import MockConfigEntry
import requests

from homeassistant.components.hikvision.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_SSL, CONF_VERIFY_SSL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, CoreState, HomeAssistant
from homeassistant.helpers import issue_registry as ir

from . import setup_integration
from .conftest import TEST_HOST, TEST_PASSWORD, TEST_PORT, TEST_USERNAME


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test successful setup and unload of config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hikcamera.return_value.start_stream.assert_called_once()

    mock_hikcamera.assert_called_once_with(
        f"http://{TEST_HOST}", TEST_PORT, TEST_USERNAME, TEST_PASSWORD, True
    )

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_hikcamera.return_value.disconnect.assert_called_once()


async def test_stream_stopped_on_shutdown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test the event stream thread is joined before the event loop closes."""
    await setup_integration(hass, mock_config_entry)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_hikcamera.return_value.disconnect.assert_called_once()


async def test_stream_stopped_when_shutdown_starts_during_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test the stream is stopped when shutdown begins while setting up."""
    hass.set_state(CoreState.stopping)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_hikcamera.return_value.disconnect.assert_called_once()


@pytest.mark.parametrize(
    ("entry_data", "expected_verify_ssl"),
    [
        ({CONF_VERIFY_SSL: False}, False),
        ({CONF_VERIFY_SSL: True}, True),
        # Entries created before the option existed keep verifying
        (None, True),
    ],
    ids=["unverified", "verified", "legacy_entry"],
)
async def test_setup_entry_ssl_verification(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    entry_data: dict[str, bool] | None,
    expected_verify_ssl: bool,
) -> None:
    """Test the certificate verification choice is passed to HikCamera."""
    data = {**mock_config_entry.data, CONF_SSL: True}
    data.pop(CONF_VERIFY_SSL)
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**data, **(entry_data or {})}
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hikcamera.assert_called_once_with(
        f"https://{TEST_HOST}",
        TEST_PORT,
        TEST_USERNAME,
        TEST_PASSWORD,
        expected_verify_ssl,
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


@pytest.mark.parametrize("amount_of_channels", [2])
@pytest.mark.parametrize("verify_ssl", [True, False])
async def test_setup_entry_nvr_channels_ssl_verification(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
    mock_hik_get_channels: MagicMock,
    verify_ssl: bool,
) -> None:
    """Test the certificate verification choice is used to list NVR channels."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_SSL: True, CONF_VERIFY_SSL: verify_ssl},
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_get_channels.assert_called_once_with(
        TEST_HOST, TEST_PORT, TEST_USERNAME, TEST_PASSWORD, True, verify_ssl
    )


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


async def test_setup_entry_nvr_skips_videoloss(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
) -> None:
    """Test NVR event injection skips videoloss (watchdog event)."""
    mock_hik_nvr.return_value.get_event_triggers.return_value = {
        "VMD": [1, 2],
        "videoloss": [1, 2, 3],
    }

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.inject_events.assert_called_once_with({"Motion": [1, 2]})


async def test_setup_entry_nvr_skips_unmapped_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test NVR event injection skips events not in SENSOR_MAP."""
    mock_hik_nvr.return_value.get_event_triggers.return_value = {
        "VMD": [1],
        "audioexception": [1, 2],
    }

    with caplog.at_level(logging.DEBUG):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.inject_events.assert_called_once_with({"Motion": [1]})
    assert "Skipping unmapped event type: audioexception" in caplog.text


async def test_setup_entry_nvr_skips_all_unknown_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
) -> None:
    """Test NVR event injection with only unknown events does not inject."""
    mock_hik_nvr.return_value.get_event_triggers.return_value = {
        "videoloss": [1],
        "audioexception": [2],
    }

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.inject_events.assert_not_called()


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


async def test_setup_with_rejected_credentials_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a rejected password asks for new credentials instead of retrying."""
    mock_hikcamera.return_value.get_id = None
    mock_hikcamera.return_value.auth_failed = True

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
    # Core also raises a repair for the entry, linking to the reauth flow.
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN,
        f"config_entry_reauth_{DOMAIN}_{mock_config_entry.entry_id}",
    )


async def test_setup_unreachable_device_is_retried(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test a device that gives no ID, without rejecting the login, is retried."""
    mock_hikcamera.return_value.get_id = None

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()
