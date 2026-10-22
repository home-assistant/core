"""Tests for the Nanoleaf integration init."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

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
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import get_reauth_flows, setup_integration

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


async def test_event_listener_is_cancelled_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nanoleaf: AsyncMock,
) -> None:
    """Test the running event listener is cancelled when the entry is unloaded."""
    started = asyncio.Event()
    cancelled = asyncio.Event()

    async def listen_events(**kwargs: object) -> None:
        """Run until cancelled, like the real listener."""
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            cancelled.set()
            raise

    mock_nanoleaf.listen_events.side_effect = listen_events

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert started.is_set()
    assert not cancelled.is_set()

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert cancelled.is_set()


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(InvalidToken("invalid"), id="invalid_token"),
        pytest.param(AuthError("auth"), id="auth_error"),
    ],
)
async def test_event_listener_auth_error_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nanoleaf: AsyncMock,
    error: AuthError,
) -> None:
    """Test a token rejected by the event stream starts the reauth flow."""
    mock_nanoleaf.listen_events.side_effect = error

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(get_reauth_flows(hass, mock_config_entry)) == 1


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(EndpointNotFoundError("events"), id="endpoint_not_found"),
        pytest.param(NanoleafConnectionError("connection"), id="connection"),
        pytest.param(NanoleafError("generic"), id="generic"),
    ],
)
async def test_event_listener_other_error_falls_back_to_polling(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_nanoleaf: AsyncMock,
    caplog: pytest.LogCaptureFixture,
    error: NanoleafError,
) -> None:
    """Test a listener that ends with another error leaves polling in place."""
    mock_nanoleaf.listen_events.side_effect = error
    mock_nanoleaf.is_on = False

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert not get_reauth_flows(hass, mock_config_entry)
    assert "falling back to polling" in caplog.text
    assert hass.states.get("light.nanoleaf").state == STATE_OFF

    # The device changes while no events arrive anymore: polling must pick it up
    mock_nanoleaf.is_on = True
    mock_nanoleaf.get_info.reset_mock()
    freezer.tick(POLL_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    mock_nanoleaf.get_info.assert_called_once()
    assert hass.states.get("light.nanoleaf").state == STATE_ON


@pytest.mark.parametrize("callback_name", ["state_callback", "effects_callback"])
async def test_pushed_event_refreshes_entities(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nanoleaf: AsyncMock,
    callback_name: str,
) -> None:
    """Test a pushed state or effect event updates the entities."""
    mock_nanoleaf.is_on = False
    await setup_integration(hass, mock_config_entry)
    assert hass.states.get("light.nanoleaf").state == STATE_OFF

    callback = mock_nanoleaf.listen_events.call_args.kwargs[callback_name]
    mock_nanoleaf.is_on = True
    await callback(MagicMock())
    await hass.async_block_till_done()

    assert hass.states.get("light.nanoleaf").state == STATE_ON
