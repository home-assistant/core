"""Tests for shared amplifier polling and per-zone results."""

import asyncio
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import timedelta
from threading import Event
from typing import Any
from unittest.mock import DEFAULT, MagicMock, call, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed
from serialx import SerialException

from homeassistant.components.monoprice.const import CONF_NOT_FIRST_RUN, DOMAIN
from homeassistant.components.monoprice.coordinator import (
    ZONE_IDS,
    MonopriceCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_CONFIG


async def _poll(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Let the shared 10 second timer fire once."""
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def _wait_for(
    hass: HomeAssistant, flag: Event, what: str, timeout: float = 5
) -> None:
    """Wait for a flag set by a worker thread, failing the test after a real timeout.

    asyncio.wait_for cannot do this: the freezer also freezes the event loop's clock,
    so its timeout never fires and a stuck worker would hang the test. A
    threading.Event times out on the real clock.
    """
    assert await hass.async_add_executor_job(flag.wait, timeout), (
        f"{what} did not happen within {timeout} seconds"
    )


async def test_enabled_zones_and_context_deduplication(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Only enabled zones are read, once each even with shared contexts."""
    assert client.zone_status.call_args_list == [call(11), call(12)]
    coordinator = entry.runtime_data.coordinator
    remove = coordinator.async_add_listener(lambda: None, context=11)
    client.zone_status.reset_mock()
    await _poll(hass, freezer)
    assert client.zone_status.call_args_list == [call(11), call(12)]
    remove()


@pytest.mark.parametrize(
    "failure", [None, SerialException("serial error"), TimeoutError("timeout")]
)
@pytest.mark.usefixtures("entry")
async def test_zone_failure_and_recovery(
    hass: HomeAssistant,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
    failure: SerialException | TimeoutError | None,
) -> None:
    """An unavailable zone does not hide a healthy sibling."""
    healthy = client.zone_status(12)
    client.zone_status.side_effect = [failure, healthy]
    await _poll(hass, freezer)
    assert hass.states.get("media_player.zone_11").state == "unavailable"
    assert hass.states.get("media_player.zone_12").state == "on"
    client.zone_status.side_effect = None
    await _poll(hass, freezer)
    assert hass.states.get("media_player.zone_11").state == "on"


@pytest.mark.usefixtures("entry")
async def test_all_zones_fail_and_recover(
    hass: HomeAssistant, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Retry all enabled zones after a complete outage."""
    client.zone_status.side_effect = SerialException
    await _poll(hass, freezer)
    assert hass.states.get("media_player.zone_11").state == "unavailable"
    assert hass.states.get("media_player.zone_12").state == "unavailable"
    client.zone_status.side_effect = None
    await _poll(hass, freezer)
    assert hass.states.get("media_player.zone_11").state == "on"
    assert hass.states.get("media_player.zone_12").state == "on"


@pytest.mark.usefixtures("entry")
async def test_ten_second_poll_despite_command(
    hass: HomeAssistant,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Targeted command read-back does not reset the other zones' timer."""
    client.zone_status.reset_mock()
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert client.zone_status.call_count == 0
    await hass.services.async_call(
        "media_player", "turn_off", {"entity_id": "media_player.zone_11"}, blocking=True
    )
    assert client.zone_status.call_args_list == [call(11)]
    assert hass.states.get("media_player.zone_11").state == "off"
    client.zone_status.reset_mock()
    freezer.tick(timedelta(seconds=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert client.zone_status.call_args_list == [call(11), call(12)]


@pytest.mark.usefixtures("entry")
async def test_command_failed_readback(hass: HomeAssistant, client: MagicMock) -> None:
    """A failed read-back affects only the target zone."""
    client.zone_status.side_effect = SerialException
    await hass.services.async_call(
        "media_player", "turn_off", {"entity_id": "media_player.zone_11"}, blocking=True
    )
    assert hass.states.get("media_player.zone_11").state == "unavailable"
    assert hass.states.get("media_player.zone_12").state == "on"


async def test_command_failure_propagates(
    entry: MockConfigEntry, client: MagicMock
) -> None:
    """Do not report a failed command as successful or read a false result."""
    client.set_power.side_effect = SerialException
    client.zone_status.reset_mock()
    with pytest.raises(SerialException):
        await entry.runtime_data.coordinator.async_command(
            11, client.set_power, 11, False
        )
    client.zone_status.assert_not_called()


async def test_command_and_poll_are_serialized(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A poll cannot run between a command and its read-back."""
    started = Event()
    release = Event()

    def command() -> None:
        started.set()
        assert release.wait(5)
        client.set_power(11, False)

    coordinator = entry.runtime_data.coordinator
    client.zone_status.reset_mock()
    task = asyncio.create_task(coordinator.async_command(11, command))
    try:
        await _wait_for(hass, started, "the command's worker starting")
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        for _ in range(10):
            await asyncio.sleep(0)
        client.zone_status.assert_not_called()
    finally:
        release.set()
    await task
    await hass.async_block_till_done(wait_background_tasks=True)
    assert client.zone_status.call_args_list == [call(11), call(11), call(12)]
    assert hass.states.get("media_player.zone_11").state == "off"


async def test_disable_reload_and_reenable(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Registry choices survive reload and newly enabled zones resume polling."""
    original_id = entity_registry.async_get("media_player.zone_11").id
    entity_registry.async_update_entity(
        "media_player.zone_11", disabled_by=er.RegistryEntryDisabler.USER
    )
    await hass.async_block_till_done()
    client.zone_status.reset_mock()
    await _poll(hass, freezer)
    assert client.zone_status.call_args_list == [call(12)]
    client.zone_status.reset_mock()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert client.zone_status.call_args_list == [call(12)]
    entity_registry.async_update_entity("media_player.zone_11", disabled_by=None)
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("media_player.zone_11").state == "on"
    assert entity_registry.async_get("media_player.zone_11").id == original_id


async def test_unload_stops_polling(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Unloading removes the shared timer."""
    assert await hass.config_entries.async_unload(entry.entry_id)
    client.zone_status.reset_mock()
    freezer.tick(timedelta(seconds=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    client.zone_status.assert_not_called()


async def test_no_enabled_zones(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """An amplifier without listeners needs no startup or recurring reads."""
    for entity_id in ("media_player.zone_11", "media_player.zone_12"):
        entity_registry.async_update_entity(
            entity_id, disabled_by=er.RegistryEntryDisabler.USER
        )
    await hass.async_block_till_done()
    client.zone_status.reset_mock()
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    client.zone_status.assert_not_called()


async def test_first_discovery_then_active_zones(
    hass: HomeAssistant,
    client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Probe optional zones once, then poll only discovered enabled players."""
    client.zone_status.side_effect = [client.zone_status(11)] * 6 + [None] * 12
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert (
        entity_registry.async_get("media_player.zone_21").disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )
    client.zone_status.side_effect = None
    client.zone_status.reset_mock()
    await _poll(hass, freezer)
    assert client.zone_status.call_args_list == [call(zone) for zone in range(11, 17)]


async def test_first_discovery_with_silent_optional_zones(
    hass: HomeAssistant, client: MagicMock, entity_registry: er.EntityRegistry
) -> None:
    """Actual serial timeouts from absent units must not prevent setup."""
    client.zone_status.side_effect = [client.zone_status(11)] * 6 + [
        TimeoutError()
    ] * 12
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get("media_player.zone_11").state == "on"
    assert (
        entity_registry.async_get("media_player.zone_21").disabled_by
        is er.RegistryEntryDisabler.INTEGRATION
    )
    assert len(hass.states.async_entity_ids("media_player")) == 6


def _hold_first_read(client: MagicMock, entered: Event, release: Event) -> None:
    """Make the next read of zone 11 block until released, then answer normally."""

    def zone_status(zone: int) -> Any:
        if zone == 11 and not release.is_set():
            entered.set()
            assert release.wait(5)
        return DEFAULT

    client.zone_status.side_effect = zone_status


async def test_unload_stops_poll_after_current_zone(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Unloading during a poll stops it at its next check, after the read in flight."""
    coordinator = entry.runtime_data.coordinator
    remove = coordinator.async_add_listener(lambda: None, context=13)
    entered = Event()
    release = Event()
    _hold_first_read(client, entered, release)
    client.zone_status.reset_mock()
    with _tracked_poll_jobs(hass) as jobs:
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        try:
            await _wait_for(hass, entered, "the poll's first read")
            assert await hass.config_entries.async_unload(entry.entry_id)
        finally:
            release.set()
        # Unloading cancelled the poll and waited for it, so the stop signal was set
        # before the held read returned. Wait for the worker itself to return.
        await _wait_for(hass, jobs[0], "the poll's worker returning")
    await hass.async_block_till_done(wait_background_tasks=True)
    remove()
    assert client.zone_status.call_args_list == [call(11)]


async def test_command_waits_for_whole_poll(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A command issued during a poll runs after the poll's last zone, not between zones."""
    coordinator = entry.runtime_data.coordinator
    remove = coordinator.async_add_listener(lambda: None, context=13)
    entered = Event()
    release = Event()
    _hold_first_read(client, entered, release)
    client.reset_mock()
    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)
    try:
        await _wait_for(hass, entered, "the poll's first read")
        task = asyncio.create_task(
            hass.services.async_call(
                "media_player",
                "turn_off",
                {"entity_id": "media_player.zone_12"},
                blocking=True,
            )
        )
        for _ in range(10):
            await asyncio.sleep(0)
        client.set_power.assert_not_called()
    finally:
        release.set()
    await task
    await hass.async_block_till_done(wait_background_tasks=True)
    remove()
    assert client.mock_calls == [
        call.zone_status(11),
        call.zone_status(12),
        call.zone_status(13),
        call.set_power(12, False),
        call.zone_status(12),
    ]


def _poll_task() -> asyncio.Task[Any]:
    """Return the background task running the scheduled poll."""
    (task,) = (
        task
        for task in asyncio.all_tasks()
        if "Monoprice" in (name := task.get_name()) and name.endswith("- refresh")
    )
    return task


@contextmanager
def _tracked_poll_jobs(hass: HomeAssistant) -> Iterator[list[Event]]:
    """Record the coordinator's executor jobs, each with a flag set when it returns.

    The flags are set from the worker thread when the job function returns, so a
    test can wait for the worker itself instead of for a fixed time.
    """
    run_in_executor = hass.async_add_executor_job
    returned: list[Event] = []

    def tracking_job(target: Callable[..., Any], *args: Any) -> asyncio.Future[Any]:
        if getattr(target, "__module__", None) != MonopriceCoordinator.__module__:
            return run_in_executor(target, *args)
        done = Event()
        returned.append(done)

        def tracked() -> Any:
            try:
                return target(*args)
            finally:
                done.set()

        return run_in_executor(tracked)

    with patch.object(hass, "async_add_executor_job", tracking_job):
        yield returned


async def test_poll_reads_every_zone_in_one_executor_job(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A poll of several zones takes one executor job, not one per zone."""
    remove = entry.runtime_data.coordinator.async_add_listener(lambda: None, context=13)
    client.zone_status.reset_mock()
    with _tracked_poll_jobs(hass) as jobs:
        await _poll(hass, freezer)
    remove()
    assert client.zone_status.call_args_list == [call(11), call(12), call(13)]
    assert len(jobs) == 1


async def test_cancelled_poll_stops_and_the_next_poll_reads_every_zone(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A cancelled poll stops at its next check, and the next poll reads every zone."""
    coordinator = entry.runtime_data.coordinator
    remove = coordinator.async_add_listener(lambda: None, context=13)
    entered = Event()
    release = Event()
    _hold_first_read(client, entered, release)
    client.zone_status.reset_mock()
    with _tracked_poll_jobs(hass) as jobs:
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        try:
            await _wait_for(hass, entered, "the poll's first read")
            task = _poll_task()
            task.cancel()
            await asyncio.wait([task])
        finally:
            release.set()
        # The stop signal was set before the held read returned, so the worker
        # sees it at its next check. Wait for the worker itself to return.
        await _wait_for(hass, jobs[0], "the poll's worker returning")
        assert client.zone_status.call_args_list == [call(11)]

        # The stop signal belongs to the cancelled poll, and the lock is free again.
        client.zone_status.reset_mock()
        await _poll(hass, freezer)
    remove()
    assert client.zone_status.call_args_list == [call(11), call(12), call(13)]
    assert hass.states.get("media_player.zone_11").state == "on"


async def test_queued_command_runs_after_cancelled_poll(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A queued command still runs when its poll is cancelled, and the poll stops."""
    remove = entry.runtime_data.coordinator.async_add_listener(lambda: None, context=13)
    entered = Event()
    release = Event()
    _hold_first_read(client, entered, release)
    client.reset_mock()
    with _tracked_poll_jobs(hass) as jobs:
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        try:
            await _wait_for(hass, entered, "the poll's first read")
            command = asyncio.create_task(
                hass.services.async_call(
                    "media_player",
                    "turn_off",
                    {"entity_id": "media_player.zone_12"},
                    blocking=True,
                )
            )
            for _ in range(10):
                await asyncio.sleep(0)
            client.set_power.assert_not_called()
            task = _poll_task()
            task.cancel()
            await asyncio.wait([task])
        finally:
            release.set()
        await command
        # The stop signal was set before the held read returned. Once the poll's
        # worker has returned, no further read of that poll can follow.
        await _wait_for(hass, jobs[0], "the poll's worker returning")
        assert client.mock_calls == [
            call.zone_status(11),
            call.set_power(12, False),
            call.zone_status(12),
        ]

        # A cancelled poll marks the update as failed until the next poll succeeds.
        await _poll(hass, freezer)
    remove()
    assert hass.states.get("media_player.zone_12").state == "off"


async def test_poll_queued_when_last_entities_are_disabled_reads_nothing(
    hass: HomeAssistant,
    entry: MockConfigEntry,
    client: MagicMock,
    entity_registry: er.EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A poll waiting for a command's lock reads nothing once no entity listens."""
    started = Event()
    release = Event()

    def command() -> None:
        started.set()
        assert release.wait(5)

    coordinator = entry.runtime_data.coordinator
    client.zone_status.reset_mock()
    task = asyncio.create_task(coordinator.async_command(11, command))
    try:
        await _wait_for(hass, started, "the command's worker starting")
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        for _ in range(10):
            await asyncio.sleep(0)
        poll = _poll_task()
        for entity_id in ("media_player.zone_11", "media_player.zone_12"):
            entity_registry.async_update_entity(
                entity_id, disabled_by=er.RegistryEntryDisabler.USER
            )
        for _ in range(50):
            await asyncio.sleep(0)
        assert not list(coordinator.async_contexts())
        assert not poll.done()
    finally:
        release.set()
    await task
    await hass.async_block_till_done(wait_background_tasks=True)
    assert poll.done()
    # Only the command's own read-back, and later timers read nothing either.
    assert client.zone_status.call_args_list == [call(11)]
    await _poll(hass, freezer)
    assert client.zone_status.call_args_list == [call(11)]


async def test_failed_first_refresh_keeps_the_startup_zones(
    hass: HomeAssistant, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """Only a first refresh that returned uses up the startup zones."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    coordinator = MonopriceCoordinator(hass, config_entry, client, (11, 12))
    # A listener without a context runs the timer but selects no zones.
    remove = coordinator.async_add_listener(lambda: None)
    client.zone_status.side_effect = RuntimeError
    await _poll(hass, freezer)
    assert not coordinator.last_update_success
    client.zone_status.side_effect = None
    client.zone_status.reset_mock()
    await _poll(hass, freezer)
    assert coordinator.last_update_success
    assert client.zone_status.call_args_list == [call(11), call(12)]
    client.zone_status.reset_mock()
    await _poll(hass, freezer)
    remove()
    client.zone_status.assert_not_called()


async def test_cancelled_first_refresh_keeps_the_startup_zones(
    hass: HomeAssistant, client: MagicMock, freezer: FrozenDateTimeFactory
) -> None:
    """A cancelled first refresh does not use up the startup zones."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG)
    config_entry.add_to_hass(hass)
    coordinator = MonopriceCoordinator(hass, config_entry, client, (11, 12))
    # A listener without a context runs the timer but selects no zones.
    remove = coordinator.async_add_listener(lambda: None)
    entered = Event()
    release = Event()
    _hold_first_read(client, entered, release)
    with _tracked_poll_jobs(hass) as jobs:
        freezer.tick(timedelta(seconds=10))
        async_fire_time_changed(hass)
        try:
            await _wait_for(hass, entered, "the first read")
            task = _poll_task()
            task.cancel()
            await asyncio.wait([task])
        finally:
            release.set()
        await _wait_for(hass, jobs[0], "the worker returning")
        assert client.zone_status.call_args_list == [call(11)]
        client.zone_status.reset_mock()
        await _poll(hass, freezer)
    remove()
    assert client.zone_status.call_args_list == [call(11), call(12)]


async def test_startup_reads_enabled_and_new_zones_once(
    hass: HomeAssistant, client: MagicMock, entity_registry: er.EntityRegistry
) -> None:
    """Setup reads the enabled and the not yet registered zones, each once."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={**MOCK_CONFIG, CONF_NOT_FIRST_RUN: True}
    )
    config_entry.add_to_hass(hass)
    for zone, disabled_by in ((11, None), (12, er.RegistryEntryDisabler.USER)):
        entity_registry.async_get_or_create(
            "media_player",
            DOMAIN,
            f"{config_entry.entry_id}_{zone}",
            suggested_object_id=f"zone_{zone}",
            config_entry=config_entry,
            disabled_by=disabled_by,
        )
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert client.zone_status.call_args_list == [
        call(zone) for zone in ZONE_IDS if zone != 12
    ]
