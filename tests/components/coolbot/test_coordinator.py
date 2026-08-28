"""Coordinator behavior: refresh, reconnect, and failure handling."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from pycoolbot import CoolbotAuthError, CoolbotError
import pytest

from homeassistant.components.coolbot.const import (
    DOMAIN,
    PROFILE_REFRESH_INTERVAL,
    UPDATE_INTERVAL,
)
from homeassistant.config_entries import ConfigEntryState
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


@pytest.mark.parametrize(
    "failure", [RuntimeError("surprise"), asyncio.CancelledError()]
)
async def test_a_connect_that_never_succeeds_closes_the_client(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    failure: BaseException,
) -> None:
    """Every way of leaving a connect attempt has to close the client.

    The socket and its reader task exist partway through connecting, before
    anything else holds the client, so an unexpected error or a cancellation
    from a reload would otherwise leak both.
    """
    mock_client.async_connect.side_effect = failure
    mock_config_entry.add_to_hass(hass)

    with suppress(Exception, asyncio.CancelledError):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is not ConfigEntryState.LOADED
    mock_client.async_close.assert_awaited()


async def test_a_cancelled_first_refresh_closes_the_client(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Cancellation mid-refresh must not leak the socket connecting opened.

    The coordinator re-raises an active CancelledError, so a reload or
    shutdown that cancels setup after the socket opened, but before
    runtime_data is assigned, leaves no unload path to close it.
    """
    mock_client.async_ping.side_effect = asyncio.CancelledError()
    mock_config_entry.add_to_hass(hass)

    with suppress(Exception, asyncio.CancelledError):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is not ConfigEntryState.LOADED
    mock_client.async_close.assert_awaited()


async def test_a_replaced_slot_does_not_resurrect_its_predecessor(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A slot left unidentified by a timed-out replay is held back.

    The client drops a slot's cached MAC when its replay times out, because
    the slot may hold replacement hardware by then. Restoring the previous
    occupant on a slot match would republish an identity the client refused
    to vouch for — and keep a replaced cooler in the data forever, where
    device removal refuses to delete it. It goes unavailable instead, and
    comes back if its own MAC ever replays.
    """
    assert await setup_integration(hass, mock_config_entry)

    mock_client.async_get_devices.return_value = [
        make_device(unique_id="coolbot_10_0", mac_address=None)
    ]
    await _tick(hass)

    assert mock_config_entry.runtime_data.data == {}
    assert "Walk-in cooler has stopped reporting" in caplog.text
    assert (
        hass.states.get("sensor.walk_in_cooler_room_temperature").state == "unavailable"
    )

    # The same cooler answering again under its own MAC is the recovery path.
    mock_client.async_get_devices.return_value = [make_device()]
    await _tick(hass)
    assert set(mock_config_entry.runtime_data.data) == {"coolbot_aabbccddeeff"}
    assert "Walk-in cooler is reporting again" in caplog.text
    assert (
        hass.states.get("sensor.walk_in_cooler_room_temperature").state != "unavailable"
    )


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


async def test_an_outage_is_logged_under_the_current_name(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A cooler renamed while healthy is logged by its current name later.

    The remembered name exists so a device that dropped out of the profile can
    still be named; it has to follow renames while the device is reporting, or
    the eventual outage line points at a cooler that no longer exists.
    """
    assert await setup_integration(hass, mock_config_entry)

    mock_client.async_get_devices.return_value = [make_device(name="Flower cooler")]
    await _tick(hass)

    mock_client.async_get_devices.return_value = []
    await _tick(hass)
    assert "Flower cooler has stopped reporting" in caplog.text


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


async def test_the_account_profile_is_reread_periodically(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Account changes have to reach a connection that never drops.

    The client reads the profile while connecting and serves the device list
    from it, so a cooler added to or removed from the account would otherwise
    go unnoticed for as long as the socket happened to last.
    """
    assert await setup_integration(hass, mock_config_entry)
    mock_client.async_refresh_profile.reset_mock()

    # Well inside the interval: the profile is a whole-account document, so it
    # is not re-read on every ten-second refresh.
    freezer.tick(UPDATE_INTERVAL + timedelta(seconds=1))
    await _tick(hass)
    mock_client.async_refresh_profile.assert_not_awaited()

    freezer.tick(PROFILE_REFRESH_INTERVAL)
    await _tick(hass)
    mock_client.async_refresh_profile.assert_awaited()


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
