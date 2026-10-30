"""Tests for the NRGkick integration initialization."""

from unittest.mock import AsyncMock

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
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.nrgkick.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

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
