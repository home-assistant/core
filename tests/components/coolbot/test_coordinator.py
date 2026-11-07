"""Coordinator behavior: refresh, reconnect, and failure handling."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
from pycoolbot import CoolbotAuthError, CoolbotError
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.coolbot.const import (
    CONNECT_TIMEOUT_SECONDS,
    DOMAIN,
    MAINTENANCE_INTERVAL,
    PROFILE_REFRESH_INTERVAL,
    STALE_AFTER_SECONDS,
)
from homeassistant.components.coolbot.coordinator import device_is_fresh
from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM

from . import push, setup_integration
from .conftest import make_client, make_device

ROOM_TEMPERATURE = "sensor.walk_in_cooler_room_temperature"


async def _request_update(hass: HomeAssistant) -> None:
    """Ask for a refresh the way a user or automation does."""
    await async_setup_component(hass, "homeassistant", {})
    await hass.services.async_call(
        "homeassistant",
        SERVICE_UPDATE_ENTITY,
        {ATTR_ENTITY_ID: ROOM_TEMPERATURE},
        blocking=True,
    )


async def _tick(hass: HomeAssistant) -> None:
    async_fire_time_changed(
        hass, dt_util.utcnow() + MAINTENANCE_INTERVAL + timedelta(seconds=1)
    )
    await hass.async_block_till_done()


async def test_the_coordinator_does_not_poll(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Readings arrive by push, so there is no update interval to drive them.

    An interval here would make the integration a poller wearing a cloud_push
    manifest, which is what the service's own protocol makes unnecessary.
    """
    assert await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.runtime_data.update_interval is None
    mock_client.add_listener.assert_called_once()


async def test_a_push_publishes_without_waiting_for_the_timer(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A reading reaches entities as it lands, not on the next tick."""
    # Assert wire values as-is rather than through metric conversion.
    hass.config.units = US_CUSTOMARY_SYSTEM
    assert await setup_integration(hass, mock_config_entry)

    mock_client.async_get_devices.return_value = [make_device(room_temp_f=41.5)]
    await push(hass, mock_client)

    assert hass.states.get("sensor.walk_in_cooler_room_temperature").state == "41.5"


async def test_a_push_after_the_client_is_gone_is_ignored(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A listener firing during teardown must not publish from a dead socket."""
    assert await setup_integration(hass, mock_config_entry)
    listeners = list(mock_client.listeners)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for listener in listeners:
        listener()  # must not raise
    await hass.async_block_till_done()


async def test_unloading_removes_the_listener(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A listener left behind would publish from a socket nobody maintains."""
    assert await setup_integration(hass, mock_config_entry)
    assert mock_client.listeners

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert not mock_client.listeners


async def test_unloading_mid_reconnect_leaves_no_socket_open(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A maintenance pass caught reconnecting by an unload installs nothing.

    Without teardown stopping the pass, the reconnect would finish after the
    unload and leave an open client and listener that nothing closes.
    """
    assert await setup_integration(hass, mock_config_entry)

    connecting = asyncio.Event()
    release = asyncio.Event()

    async def blocked_connect() -> None:
        connecting.set()
        await release.wait()

    mock_client.connected = False
    mock_client.async_connect.side_effect = blocked_connect
    async_fire_time_changed(
        hass, dt_util.utcnow() + MAINTENANCE_INTERVAL + timedelta(seconds=1)
    )
    await connecting.wait()
    mock_client.async_close.reset_mock()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    release.set()
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not mock_client.listeners
    mock_client.async_close.assert_awaited()


async def test_stopping_home_assistant_closes_the_socket(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Entries are not unloaded on stop, so the coordinator tears down itself.

    Otherwise the timer would keep starting passes during the stop, and a
    reconnect among them would hold the stop up. An unload afterwards must
    not try to remove the stop listener that has already run.
    """
    assert await setup_integration(hass, mock_config_entry)
    mock_client.async_close.reset_mock()

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_client.async_close.assert_awaited_once()
    assert not mock_client.listeners

    mock_client.connected = False
    await _tick(hass)
    mock_client.async_connect.assert_awaited_once()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert "Unable to remove unknown job listener" not in caplog.text


async def test_unloading_while_the_old_socket_closes_does_not_reconnect(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A close that swallows the unload's cancellation must not lead to a connect.

    The library's close awaits its reader task and catches CancelledError, so
    cancelling the pass there can be lost, and the pass would go on to open a
    new socket the unload then has to wait for.
    """
    assert await setup_integration(hass, mock_config_entry)

    closing = asyncio.Event()

    async def close_swallowing_cancellation() -> None:
        closing.set()
        with suppress(asyncio.CancelledError):
            await asyncio.Event().wait()

    mock_client.connected = False
    mock_client.async_close.side_effect = close_swallowing_cancellation
    created: list[AsyncMock] = []

    def new_client(*args: object, **kwargs: object) -> AsyncMock:
        created.append(make_client())
        return created[-1]

    with patch(
        "homeassistant.components.coolbot.coordinator.CoolbotClient", new_client
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + MAINTENANCE_INTERVAL + timedelta(seconds=1)
        )
        await closing.wait()

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    assert not created


async def test_a_slow_maintenance_pass_is_not_overlapped(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A tick that lands while a pass is still running does not start another."""
    assert await setup_integration(hass, mock_config_entry)

    pinging = asyncio.Event()
    release = asyncio.Event()

    async def slow_ping() -> None:
        pinging.set()
        await release.wait()

    mock_client.async_ping.side_effect = slow_ping
    mock_client.async_ping.reset_mock()
    async_fire_time_changed(
        hass, dt_util.utcnow() + MAINTENANCE_INTERVAL + timedelta(seconds=1)
    )
    await pinging.wait()
    async_fire_time_changed(
        hass, dt_util.utcnow() + 2 * MAINTENANCE_INTERVAL + timedelta(seconds=2)
    )
    release.set()
    await hass.async_block_till_done()

    assert mock_client.async_ping.await_count == 1


class _BlockedClients:
    """Hand out a fresh client per connect, each held until released."""

    def __init__(self) -> None:
        self.created: list[AsyncMock] = []
        self.connecting = asyncio.Event()
        self.release = asyncio.Event()

    def __call__(self, *args: object, **kwargs: object) -> AsyncMock:
        client = make_client()

        async def blocked_connect() -> None:
            self.connecting.set()
            await self.release.wait()

        client.async_connect.side_effect = blocked_connect
        self.created.append(client)
        return client


async def test_overlapping_reconnects_open_one_client(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Maintenance and a refresh that both find the socket down share a reconnect.

    Two connects would leave whichever client the other replaced open, with its
    listener still attached, after the entry is unloaded.
    """
    assert await setup_integration(hass, mock_config_entry)
    mock_client.connected = False
    clients = _BlockedClients()

    with patch("homeassistant.components.coolbot.coordinator.CoolbotClient", clients):
        async_fire_time_changed(
            hass, dt_util.utcnow() + MAINTENANCE_INTERVAL + timedelta(seconds=1)
        )
        await clients.connecting.wait()
        hass.async_create_task(_request_update(hass))
        for _ in range(20):
            await asyncio.sleep(0)
        clients.release.set()
        await hass.async_block_till_done()

    assert len(clients.created) == 1

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for client in clients.created:
        client.async_close.assert_awaited()
        assert not client.listeners


async def test_unloading_mid_refresh_reconnect_leaves_no_socket_open(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A refresh caught reconnecting by an unload closes the client it opened."""
    assert await setup_integration(hass, mock_config_entry)
    mock_client.connected = False
    clients = _BlockedClients()

    with patch("homeassistant.components.coolbot.coordinator.CoolbotClient", clients):
        hass.async_create_task(_request_update(hass))
        await clients.connecting.wait()
        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        clients.release.set()
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    (client,) = clients.created
    client.async_close.assert_awaited()
    assert not client.listeners


@pytest.mark.parametrize(
    "outcome",
    [CoolbotError("dropped"), CoolbotAuthError("rejected"), None],
    ids=["connection_error", "auth_error", "success"],
)
async def test_a_superseded_maintenance_pass_leaves_the_replacement_alone(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    outcome: Exception | None,
) -> None:
    """A pass still waiting on a client a refresh has replaced changes nothing.

    Its result belongs to a socket already closed: acting on a failure would
    close the healthy replacement and mark recovered sensors unavailable.
    """
    assert await setup_integration(hass, mock_config_entry)

    pinging = asyncio.Event()
    release = asyncio.Event()

    async def slow_ping() -> None:
        pinging.set()
        await release.wait()
        if outcome is not None:
            raise outcome

    mock_client.async_ping.side_effect = slow_ping
    async_fire_time_changed(
        hass, dt_util.utcnow() + MAINTENANCE_INTERVAL + timedelta(seconds=1)
    )
    await pinging.wait()

    mock_client.connected = False
    replacement = make_client()
    with patch(
        "homeassistant.components.coolbot.coordinator.CoolbotClient",
        return_value=replacement,
    ):
        await _request_update(hass)
    release.set()
    await hass.async_block_till_done()

    replacement.async_close.assert_not_awaited()
    assert replacement.listeners
    assert hass.states.get(ROOM_TEMPERATURE).state != "unavailable"
    assert mock_config_entry.runtime_data.last_update_success


@pytest.mark.parametrize(
    "error",
    [CoolbotError("dropped"), CoolbotAuthError("rejected")],
    ids=["connection_error", "auth_error"],
)
async def test_a_reconnect_during_a_failed_pass_close_stays_healthy(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    error: Exception,
) -> None:
    """A refresh that reconnects while a failed pass closes its socket wins.

    The pass's error has to be published before that close is awaited, or it
    lands after the refresh and marks the healthy replacement unavailable.
    """
    assert await setup_integration(hass, mock_config_entry)

    closing = asyncio.Event()
    release = asyncio.Event()

    async def slow_close() -> None:
        closing.set()
        await release.wait()

    mock_client.async_ping.side_effect = error
    mock_client.async_close.side_effect = slow_close
    async_fire_time_changed(
        hass, dt_util.utcnow() + MAINTENANCE_INTERVAL + timedelta(seconds=1)
    )
    await closing.wait()

    replacement = make_client()
    with patch(
        "homeassistant.components.coolbot.coordinator.CoolbotClient",
        return_value=replacement,
    ):
        await _request_update(hass)
    release.set()
    await hass.async_block_till_done()

    assert mock_config_entry.runtime_data.last_update_success
    assert hass.states.get(ROOM_TEMPERATURE).state != "unavailable"


async def test_a_refresh_that_cannot_reconnect_fails(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """An explicit refresh has to reconnect too, and can fail doing it.

    Nothing refreshes on a schedule any more, but a reload or a caller asking
    for one still arrives here, and the socket may have died meanwhile.
    """
    assert await setup_integration(hass, mock_config_entry)

    mock_client.connected = False
    mock_client.async_connect.side_effect = CoolbotError("unreachable")
    await _request_update(hass)

    assert not mock_config_entry.runtime_data.last_update_success


async def test_a_refresh_rejected_by_the_service_fails(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Credentials rejected while reconnecting for a refresh stop the updates."""
    assert await setup_integration(hass, mock_config_entry)

    mock_client.connected = False
    mock_client.async_connect.side_effect = CoolbotAuthError("rejected")
    await _request_update(hass)

    assert not mock_config_entry.runtime_data.last_update_success
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)


def test_an_unprovisioned_device_is_never_fresh() -> None:
    """An empty slot has no readings to trust, however recently it answered.

    The service keeps serving plausible values for slots no cooler occupies, so
    this guard is what stops them being published as a live temperature.
    """
    device = make_device(is_provisioned=False, last_data_at=dt_util.utcnow())
    assert not device_is_fresh(device)


async def test_maintenance_pings_to_keep_the_socket_alive(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """The timer exists to hold the connection open, not to fetch readings."""
    assert await setup_integration(hass, mock_config_entry)
    mock_client.async_ping.reset_mock()

    await _tick(hass)
    mock_client.async_ping.assert_awaited()


async def test_dropped_socket_reconnects_on_next_maintenance(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A dead socket is replaced transparently on the next cycle."""
    assert await setup_integration(hass, mock_config_entry)
    assert mock_client.async_connect.await_count == 1

    mock_client.connected = False
    await _tick(hass)

    assert mock_client.async_connect.await_count == 2
    assert mock_config_entry.runtime_data.last_update_success


async def test_a_stalled_reconnect_fails_in_time(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A reconnect that hangs gives up before the readings would go stale.

    Nothing is published while it hangs, so without a limit the last
    temperature would stay on screen for as long as the connect took.
    """
    assert await setup_integration(hass, mock_config_entry)
    mock_client.connected = False
    clients = _BlockedClients()

    with patch("homeassistant.components.coolbot.coordinator.CoolbotClient", clients):
        async_fire_time_changed(
            hass, dt_util.utcnow() + MAINTENANCE_INTERVAL + timedelta(seconds=1)
        )
        await clients.connecting.wait()
        assert mock_config_entry.runtime_data.last_update_success

        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + MAINTENANCE_INTERVAL
            + timedelta(seconds=CONNECT_TIMEOUT_SECONDS + 1),
        )
        # Not async_block_till_done: a pass the tick starts would block too.
        for _ in range(20):
            await asyncio.sleep(0)

        assert not mock_config_entry.runtime_data.last_update_success
        assert hass.states.get(ROOM_TEMPERATURE).state == "unavailable"
        clients.created[0].async_close.assert_awaited()

        clients.release.set()
        await hass.async_block_till_done()


async def test_staleness_is_rechecked_while_a_pass_is_held_up(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A cooler goes unavailable on time even while a pass waits on the network.

    Ticks that find a pass still running start no new one, so without a
    recheck there the last reading would stay on screen until the pass ended.
    """
    assert await setup_integration(hass, mock_config_entry)

    pinging = asyncio.Event()
    release = asyncio.Event()

    async def blocked_ping() -> None:
        pinging.set()
        await release.wait()

    mock_client.async_ping.side_effect = blocked_ping
    freezer.tick(MAINTENANCE_INTERVAL + timedelta(seconds=1))
    async_fire_time_changed(hass)
    await pinging.wait()
    assert hass.states.get(ROOM_TEMPERATURE).state != "unavailable"

    freezer.tick(timedelta(seconds=STALE_AFTER_SECONDS))
    async_fire_time_changed(hass)
    for _ in range(20):
        await asyncio.sleep(0)

    assert hass.states.get(ROOM_TEMPERATURE).state == "unavailable"
    # Only the readings are stale; the service itself has not failed.
    assert mock_config_entry.runtime_data.last_update_success

    release.set()
    await hass.async_block_till_done()


async def test_failed_maintenance_marks_data_stale_then_recovers(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A failed cycle drops the client so the next one starts clean."""
    assert await setup_integration(hass, mock_config_entry)

    mock_client.async_ping.side_effect = CoolbotError("socket lost")
    await _tick(hass)
    assert not mock_config_entry.runtime_data.last_update_success
    mock_client.async_close.assert_awaited()

    mock_client.async_ping.side_effect = None
    mock_client.connected = False  # the old socket is gone
    await _tick(hass)
    assert mock_config_entry.runtime_data.last_update_success


async def test_recovery_after_a_failed_maintenance_pass_is_logged(
    hass: HomeAssistant,
    mock_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The end of an outage is logged, not just its start."""
    assert await setup_integration(hass, mock_config_entry)

    mock_client.async_ping.side_effect = CoolbotError("socket lost")
    await _tick(hass)
    assert "Error requesting coolbot data" in caplog.text
    assert "Fetching coolbot data recovered" not in caplog.text

    mock_client.async_ping.side_effect = None
    mock_client.connected = False  # the old socket is gone
    await _tick(hass)
    assert caplog.text.count("Fetching coolbot data recovered") == 1

    # Healthy passes and pushes after the recovery stay quiet.
    await _tick(hass)
    await push(hass, mock_client)
    assert caplog.text.count("Fetching coolbot data recovered") == 1


async def test_auth_failure_during_maintenance_closes_the_socket(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Credentials failing mid-flight stop the updates and drop the socket.

    Nothing useful can happen until the password is fixed, so the socket must
    not be left open for however long that takes. No reauth flow starts yet;
    that arrives in a follow-up PR, which is also why this does not raise
    ConfigEntryAuthFailed: it would offer a repair that cannot open.
    """
    assert await setup_integration(hass, mock_config_entry)
    mock_client.async_close.reset_mock()

    mock_client.async_ping.side_effect = CoolbotAuthError("expired")
    await _tick(hass)

    assert not mock_config_entry.runtime_data.last_update_success
    assert not hass.config_entries.flow.async_progress_by_handler(DOMAIN)
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
    mock_client.get_devices.side_effect = asyncio.CancelledError()
    mock_config_entry.add_to_hass(hass)

    with suppress(Exception, asyncio.CancelledError):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is not ConfigEntryState.LOADED
    mock_client.async_close.assert_awaited()


async def test_a_replaced_slot_does_not_resurrect_its_predecessor(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
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
    assert (
        hass.states.get("sensor.walk_in_cooler_room_temperature").state == "unavailable"
    )

    # The same cooler answering again under its own MAC is the recovery path.
    mock_client.async_get_devices.return_value = [make_device()]
    await _tick(hass)
    assert set(mock_config_entry.runtime_data.data) == {"coolbot_aabbccddeeff"}
    assert (
        hass.states.get("sensor.walk_in_cooler_room_temperature").state != "unavailable"
    )


async def test_a_device_waits_for_its_mac_identity(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """A provisioned device whose MAC pin has not replayed yet is held back.

    Its unique_id would be a dash/slot fallback that changes once the MAC
    arrives, which would duplicate the device. No entities are created for it,
    so no believable readings are published under a throwaway identity.
    """
    mock_client.async_get_devices.return_value = [
        make_device(unique_id="coolbot_10_0", mac_address=None)
    ]
    assert await setup_integration(hass, mock_config_entry)

    assert not mock_config_entry.runtime_data.data
    assert hass.states.get("sensor.walk_in_cooler_room_temperature") is None

    # Once the MAC replays, the cooler gets its sensors without a reload.
    mock_client.async_get_devices.return_value = [make_device()]
    await push(hass, mock_client)
    assert set(mock_config_entry.runtime_data.data) == {"coolbot_aabbccddeeff"}
    assert hass.states.get("sensor.walk_in_cooler_room_temperature").state != (
        "unavailable"
    )


async def test_a_device_dropping_out_of_the_profile_goes_unavailable(
    hass: HomeAssistant, mock_client: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Vanishing from a refresh is the other way a device goes unavailable."""
    assert await setup_integration(hass, mock_config_entry)

    mock_client.async_get_devices.return_value = [
        make_device(unique_id="coolbot_other", name="Other")
    ]
    await _tick(hass)
    assert hass.states.get(ROOM_TEMPERATURE).state == "unavailable"

    mock_client.async_get_devices.return_value = [make_device()]
    await _tick(hass)
    assert hass.states.get(ROOM_TEMPERATURE).state != "unavailable"


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
    freezer.tick(MAINTENANCE_INTERVAL + timedelta(seconds=1))
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
