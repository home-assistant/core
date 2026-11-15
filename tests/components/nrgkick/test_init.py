"""Tests for the NRGkick integration initialization."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from nrgkick_api import (
    NRGkickAPIDisabledError,
    NRGkickAuthenticationError,
    NRGkickConnectionError,
    NRGkickHTTPError,
    NRGkickInvalidResponseError,
    NRGkickTimeoutError,
    NRGkickUnreachableError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nrgkick.const import DEFAULT_SCAN_INTERVAL, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from . import setup_integration


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
) -> None:
    """Test successful load and unload of entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "state", "translation_key", "translation_placeholders"),
    [
        (
            NRGkickAuthenticationError("Unauthorized"),
            ConfigEntryState.SETUP_ERROR,
            "authentication_error",
            None,
        ),
        (
            NRGkickAPIDisabledError("API disabled"),
            ConfigEntryState.SETUP_ERROR,
            "json_api_disabled",
            None,
        ),
        (
            NRGkickTimeoutError("Timed out"),
            ConfigEntryState.SETUP_RETRY,
            "timeout",
            None,
        ),
        (
            NRGkickUnreachableError("Connection refused"),
            ConfigEntryState.SETUP_RETRY,
            "unreachable",
            None,
        ),
        (
            NRGkickHTTPError("Service Unavailable", status=503),
            ConfigEntryState.SETUP_RETRY,
            "http_error",
            {"status": "503"},
        ),
        (
            NRGkickConnectionError("Server disconnected"),
            ConfigEntryState.SETUP_RETRY,
            "communication_error",
            None,
        ),
        (
            NRGkickInvalidResponseError("Bad payload"),
            ConfigEntryState.SETUP_RETRY,
            "invalid_response",
            None,
        ),
    ],
)
async def test_entry_setup_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    exception: Exception,
    state: ConfigEntryState,
    translation_key: str,
    translation_placeholders: dict[str, str] | None,
) -> None:
    """Test setup entry with failed connection."""
    mock_nrgkick_api.get_info.side_effect = exception

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is state
    assert mock_config_entry.error_reason_translation_key == translation_key
    assert (
        mock_config_entry.error_reason_translation_placeholders
        == translation_placeholders
    )


async def test_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    device_registry: dr.DeviceRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test successful load and unload of entry."""
    await setup_integration(hass, mock_config_entry)

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_config_entry.unique_id), mock_config_entry.entry_id
    )
    assert device is not None
    assert device == snapshot


async def test_json_api_disabled_at_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a repair issue is created and a reload recovers once the API is enabled."""
    mock_nrgkick_api.get_info.side_effect = NRGkickAPIDisabledError("API disabled")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    issue_id = f"json_api_disabled_{mock_config_entry.entry_id}"
    assert (issue := issue_registry.async_get_issue(DOMAIN, issue_id))
    assert issue.config_entry_id == mock_config_entry.entry_id
    assert issue.translation_key == "json_api_disabled"
    assert issue.translation_placeholders == {"device_name": mock_config_entry.title}
    assert issue.severity is ir.IssueSeverity.ERROR
    assert not issue.is_fixable

    # The user enables the JSON API again and reloads the integration.
    mock_nrgkick_api.get_info.side_effect = None
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


async def test_json_api_disabled_at_runtime(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nrgkick_api: AsyncMock,
    issue_registry: ir.IssueRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a repair issue while running, which is removed once the API is enabled."""
    await setup_integration(hass, mock_config_entry)
    issue_id = f"json_api_disabled_{mock_config_entry.entry_id}"
    entity_id = "sensor.nrgkick_test_status"
    assert (state := hass.states.get(entity_id))
    assert state.state != STATE_UNAVAILABLE

    mock_nrgkick_api.get_info.side_effect = NRGkickAPIDisabledError("API disabled")
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE
    assert issue_registry.async_get_issue(DOMAIN, issue_id)

    mock_nrgkick_api.get_info.side_effect = None
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state != STATE_UNAVAILABLE
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
