"""Coordinator behavior: refresh, reconnect, and failure handling."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock

from pycoolbot import CoolbotAuthError, CoolbotError
import pytest

from homeassistant.components.coolbot.const import DOMAIN, UPDATE_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from . import setup_integration
from .conftest import make_device

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
    """Credentials failing mid-flight prompt the user rather than looping.

    Refreshes stop until reauth completes, so the socket is closed rather than
    left open for however long that takes.
    """
    assert await setup_integration(hass, mock_config_entry)
    mock_client.async_close.reset_mock()

    mock_client.async_get_devices.side_effect = CoolbotAuthError("expired")
    await _tick(hass)

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert any(flow["context"]["source"] == "reauth" for flow in flows)
    mock_client.async_close.assert_awaited()


async def test_a_device_waits_for_its_mac_identity(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A provisioned device whose MAC pin has not replayed yet is held back.

    Its unique_id would be a dash/slot fallback that changes once the MAC
    arrives, which would duplicate the device. It appears on a later refresh
    under its stable identity instead.
    """
    mock_client.async_get_devices.return_value = [
        make_device(unique_id="coolbot_10_0", mac_address=None)
    ]
    assert await setup_integration(hass, mock_config_entry)
    assert not mock_config_entry.runtime_data.data

    mock_client.async_get_devices.return_value = [make_device()]
    await _tick(hass)
    assert set(mock_config_entry.runtime_data.data) == {"coolbot_aabbccddeeff"}


async def test_startup_replay_is_not_logged_as_an_outage(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A device that has not reported yet is not an outage.

    Readings are untrusted until the first live push, which normally lands
    within 15s of setup; logging that as a failure and recovery would be noise
    on every single startup.
    """
    mock_client.async_get_devices.return_value = [make_device(last_data_at=None)]
    assert await setup_integration(hass, mock_config_entry)
    assert "has stopped reporting" not in caplog.text

    mock_client.async_get_devices.return_value = [make_device()]
    await _tick(hass)
    assert "is reporting again" not in caplog.text


async def test_staleness_is_logged_once_in_each_direction(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A device going stale is logged once, and once again on recovery."""
    assert await setup_integration(hass, mock_config_entry)

    mock_client.async_get_devices.return_value = [
        make_device(last_data_at=dt_util.utcnow() - timedelta(minutes=10))
    ]
    await _tick(hass)
    assert "has stopped reporting" in caplog.text

    caplog.clear()
    await _tick(hass)
    assert "has stopped reporting" not in caplog.text

    mock_client.async_get_devices.return_value = [make_device()]
    await _tick(hass)
    assert "is reporting again" in caplog.text


async def test_a_device_dropping_out_of_the_profile_is_logged(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Vanishing from a refresh is the other way a device goes unavailable.

    Nothing iterating the refreshed devices can see this one, since it is no
    longer among them.
    """
    assert await setup_integration(hass, mock_config_entry)

    mock_client.async_get_devices.return_value = [
        make_device(unique_id="coolbot_other", name="Other")
    ]
    await _tick(hass)
    assert "Walk-in cooler has stopped reporting" in caplog.text

    caplog.clear()
    await _tick(hass)
    assert "has stopped reporting" not in caplog.text

    mock_client.async_get_devices.return_value = [make_device()]
    await _tick(hass)
    assert "Walk-in cooler is reporting again" in caplog.text


async def test_an_emptied_account_is_a_valid_update(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Removing the last cooler produces a successful, empty update.

    Treating an empty profile as a failure would retain the previous devices
    for good, which leaves the removed cooler permanently undeletable and a
    reload stuck in setup retry.
    """
    assert await setup_integration(hass, mock_config_entry)

    mock_client.async_get_devices.return_value = []
    await _tick(hass)

    assert mock_config_entry.runtime_data.last_update_success
    assert mock_config_entry.runtime_data.data == {}
    assert (
        hass.states.get("sensor.walk_in_cooler_room_temperature").state == "unavailable"
    )
