"""Tests for the Nanoleaf coordinator."""

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

NANOLEAF_ERRORS = [
    pytest.param(Unavailable("unavailable"), id="unavailable"),
    pytest.param(NanoleafConnectionError("connection"), id="connection"),
    pytest.param(NanoleafTimeoutError("timeout"), id="timeout"),
    pytest.param(InvalidResponseError("response"), id="invalid_response"),
    pytest.param(EndpointNotFoundError("effects"), id="endpoint_not_found"),
    pytest.param(Unauthorized("pairing"), id="unauthorized"),
    pytest.param(NanoleafError("generic"), id="generic"),
]

AUTH_ERRORS = [
    pytest.param(InvalidToken("invalid"), id="invalid_token"),
    pytest.param(AuthError("auth"), id="auth_error"),
    pytest.param(NoAuthToken("missing"), id="no_token"),
]


@pytest.mark.parametrize("error", NANOLEAF_ERRORS)
async def test_first_refresh_nanoleaf_error_retries_setup(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: NanoleafError,
) -> None:
    """Test a failing first refresh is retried and does not start reauth."""
    mock_nanoleaf.get_info.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not get_reauth_flows(hass, mock_config_entry)


@pytest.mark.parametrize("error", AUTH_ERRORS)
async def test_first_refresh_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: NanoleafError,
) -> None:
    """Test a rejected token during setup starts the reauth flow."""
    mock_nanoleaf.get_info.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert len(get_reauth_flows(hass, mock_config_entry)) == 1


@pytest.mark.parametrize("error", NANOLEAF_ERRORS)
async def test_poll_nanoleaf_error_makes_entities_unavailable_and_recovers(
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
async def test_poll_auth_error_starts_reauth(
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
