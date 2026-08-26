"""Coordinator behavior: refresh, reconnect, and failure handling."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from pycoolbot import CoolbotAuthError, CoolbotError

from homeassistant.components.coolbot.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed


async def _tick(hass: HomeAssistant) -> None:
    async_fire_time_changed(
        hass, dt_util.utcnow() + UPDATE_INTERVAL + timedelta(seconds=1)
    )
    await hass.async_block_till_done()


async def test_refresh_pings_to_keep_the_socket_alive(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Every refresh pings, doubling as the keepalive."""
    assert await setup_integration(hass, mock_config_entry)
    mock_client.async_ping.reset_mock()

    await _tick(hass)
    mock_client.async_ping.assert_awaited()


async def test_dropped_socket_reconnects_on_next_refresh(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A dead socket is replaced transparently on the next cycle."""
    assert await setup_integration(hass, mock_config_entry)
    assert mock_client.async_connect.await_count == 1

    mock_client.connected = False
    await _tick(hass)

    assert mock_client.async_connect.await_count == 2
    assert mock_config_entry.runtime_data.last_update_success


async def test_failed_refresh_marks_data_stale_then_recovers(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A failed refresh drops the client so the next cycle starts clean."""
    assert await setup_integration(hass, mock_config_entry)

    mock_client.async_get_devices.side_effect = CoolbotError("socket lost")
    await _tick(hass)
    assert not mock_config_entry.runtime_data.last_update_success
    # The failure dropped the client so the next cycle starts clean.
    mock_client.async_close.assert_awaited()

    mock_client.async_get_devices.side_effect = None
    mock_client.connected = False  # the old socket is gone
    await _tick(hass)
    assert mock_config_entry.runtime_data.last_update_success


async def test_auth_failure_during_refresh_starts_reauth(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Credentials failing mid-flight prompt the user rather than looping."""
    assert await setup_integration(hass, mock_config_entry)

    mock_client.async_get_devices.side_effect = CoolbotAuthError("expired")
    await _tick(hass)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(flow["context"]["source"] == "reauth" for flow in flows)


async def test_an_empty_device_list_is_a_failure_not_a_wipe(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Zero devices means the profile fetch broke.

    Keeping the previous data (and flagging the failure) beats deleting every
    entity's state.
    """
    assert await setup_integration(hass, mock_config_entry)

    mock_client.async_get_devices.return_value = []
    await _tick(hass)

    assert not mock_config_entry.runtime_data.last_update_success
    assert mock_config_entry.runtime_data.data  # previous devices retained
