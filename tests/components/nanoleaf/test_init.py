"""Tests for the Nanoleaf integration init."""

from datetime import timedelta
from unittest.mock import AsyncMock

from aionanoleaf2 import (
    AuthError,
    EndpointNotFoundError,
    InvalidResponseError,
    InvalidToken,
    NanoleafConnectionError,
    NanoleafError,
    NanoleafTimeoutError,
    NoAuthToken,
    Unauthorized,
    Unavailable,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import get_reauth_flows, setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

# The coordinator polls every minute; add a second for the update jitter
POLL_INTERVAL = timedelta(minutes=1, seconds=1)

# Library errors that mean "the device cannot be used right now"
NANOLEAF_ERRORS = [
    pytest.param(Unavailable("unavailable"), id="unavailable"),
    pytest.param(NanoleafConnectionError("connection"), id="connection"),
    pytest.param(NanoleafTimeoutError("timeout"), id="timeout"),
    pytest.param(InvalidResponseError("response"), id="invalid_response"),
    pytest.param(EndpointNotFoundError("effects"), id="endpoint_not_found"),
    pytest.param(Unauthorized("pairing"), id="unauthorized"),
    pytest.param(NanoleafError("generic"), id="generic"),
]

# Library errors that mean "the access token is not accepted"
AUTH_ERRORS = [
    pytest.param(InvalidToken("invalid"), id="invalid_token"),
    pytest.param(AuthError("auth"), id="auth_error"),
    pytest.param(NoAuthToken("missing"), id="no_token"),
]


async def test_setup_entry_without_event_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nanoleaf: AsyncMock,
) -> None:
    """Test setup entry when device does not support events."""
    mock_nanoleaf.supports_events = False
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_nanoleaf.listen_events.assert_not_called()


async def test_setup_entry_with_event_support(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nanoleaf: AsyncMock,
) -> None:
    """Test setup entry when device supports events."""
    mock_nanoleaf.supports_events = True
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_nanoleaf.listen_events.assert_called_once()


@pytest.mark.parametrize("error", NANOLEAF_ERRORS)
async def test_setup_entry_update_failure_retries_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nanoleaf: AsyncMock,
    error: NanoleafError,
) -> None:
    """Test setup is retried when the first refresh fails, without reauth."""
    mock_nanoleaf.get_info.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "cannot_connect"
    assert not get_reauth_flows(hass, mock_config_entry)


@pytest.mark.parametrize("error", AUTH_ERRORS)
async def test_setup_entry_auth_failure_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nanoleaf: AsyncMock,
    error: NanoleafError,
) -> None:
    """Test a rejected token during setup starts the reauth flow."""
    mock_nanoleaf.get_info.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "invalid_token"
    assert len(get_reauth_flows(hass, mock_config_entry)) == 1


@pytest.mark.parametrize("error", NANOLEAF_ERRORS)
async def test_update_failure_makes_entities_unavailable_and_recovers(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: NanoleafError,
) -> None:
    """Test a failing poll marks entities unavailable until the device is back."""
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("light.nanoleaf").state != STATE_UNAVAILABLE

    mock_nanoleaf.get_info.side_effect = error
    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("light.nanoleaf").state == STATE_UNAVAILABLE
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not get_reauth_flows(hass, mock_config_entry)

    mock_nanoleaf.get_info.side_effect = None
    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get("light.nanoleaf").state != STATE_UNAVAILABLE


@pytest.mark.parametrize("error", AUTH_ERRORS)
async def test_update_auth_failure_starts_reauth(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: NanoleafError,
) -> None:
    """Test a token rejected during a poll starts the reauth flow."""
    await setup_integration(hass, mock_config_entry)
    assert not get_reauth_flows(hass, mock_config_entry)

    mock_nanoleaf.get_info.side_effect = error
    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert len(get_reauth_flows(hass, mock_config_entry)) == 1
    assert hass.states.get("light.nanoleaf").state == STATE_UNAVAILABLE
