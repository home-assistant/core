"""The tests for denonavr's coordinator module-level refresh functions."""

import asyncio
from collections.abc import Awaitable, Callable
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from denonavr.exceptions import (
    AvrCommandError,
    AvrIncompleteResponseError,
    AvrNetworkError,
)
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.denonavr.const import DOMAIN
from homeassistant.components.denonavr.coordinator import (
    DenonAvrDataUpdateCoordinator,
    async_refresh_audyssey,
    async_refresh_status,
    mark_unavailable,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed

# Both refresh functions carry the same per-zone contract, so each case below
# runs against both.
REFRESH_FUNCTIONS = pytest.mark.parametrize(
    ("refresh", "update_method"),
    [
        pytest.param(async_refresh_status, "async_update", id="status"),
        pytest.param(async_refresh_audyssey, "async_update_audyssey", id="audyssey"),
    ],
)


def _receiver_with_zones() -> tuple[MagicMock, MagicMock]:
    """Build a fake receiver with a Main and a Zone2 zone."""
    main = MagicMock()
    main.name = "Main Receiver"
    main.telnet_connected = False
    main.telnet_healthy = False
    main.async_update = AsyncMock()
    main.async_update_audyssey = AsyncMock()
    zone2 = MagicMock()
    zone2.zone = "Zone2"
    zone2.async_update = AsyncMock()
    zone2.async_update_audyssey = AsyncMock()
    main.zones = {"Main": main, "Zone2": zone2}
    return main, zone2


@REFRESH_FUNCTIONS
async def test_refresh_reaches_every_zone(
    refresh: Callable[..., Awaitable[None]], update_method: str
) -> None:
    """Each zone caches its own state.

    Both update calls only touch the zone they are called on, so Zone2 and
    Zone3 would otherwise never be refreshed.
    """
    main, zone2 = _receiver_with_zones()

    await refresh(main)

    getattr(main, update_method).assert_awaited_once()
    getattr(zone2, update_method).assert_awaited_once()


@REFRESH_FUNCTIONS
async def test_refresh_skips_every_zone_when_telnet_healthy(
    refresh: Callable[..., Awaitable[None]], update_method: str
) -> None:
    """The Telnet-healthy skip applies to every zone at once, checked only once."""
    main, zone2 = _receiver_with_zones()
    main.telnet_connected = True
    main.telnet_healthy = True

    await refresh(main)

    getattr(main, update_method).assert_not_awaited()
    getattr(zone2, update_method).assert_not_awaited()


@REFRESH_FUNCTIONS
async def test_refresh_continues_after_one_zones_command_error(
    refresh: Callable[..., Awaitable[None]], update_method: str
) -> None:
    """A rejected command in one zone doesn't abort the others.

    Zones do not all support the same settings, and one zone's
    AvrCommandError shouldn't leave the rest unrefreshed.
    """
    main, zone2 = _receiver_with_zones()
    getattr(main, update_method).side_effect = AvrCommandError("not supported", "Get")

    await refresh(main)

    getattr(zone2, update_method).assert_awaited_once()


@REFRESH_FUNCTIONS
async def test_refresh_stops_every_zone_on_a_connectivity_error(
    refresh: Callable[..., Awaitable[None]], update_method: str
) -> None:
    """A connectivity error means the receiver itself is unreachable.

    It re-raises so the whole update fails, rather than the remaining zones
    each reporting the same failure.
    """
    main, zone2 = _receiver_with_zones()
    getattr(main, update_method).side_effect = AvrNetworkError("Network error", "test")

    with pytest.raises(AvrNetworkError):
        await refresh(main)

    getattr(zone2, update_method).assert_not_awaited()


async def test_audyssey_refresh_tolerates_a_receiver_without_audyssey() -> None:
    """A receiver that does not know the query answers it short.

    denonavr tolerates the AvrProcessingError form of that but not this one,
    and a missing feature is not an unreachable receiver.
    """
    main, zone2 = _receiver_with_zones()
    main.async_update_audyssey.side_effect = AvrIncompleteResponseError(
        "Invalid length of response XML", "test"
    )

    await async_refresh_audyssey(main)

    zone2.async_update_audyssey.assert_awaited_once()


async def test_status_refresh_still_fails_on_an_incomplete_response() -> None:
    """Only the Audyssey query carries a tag a receiver may not know."""
    main, zone2 = _receiver_with_zones()
    main.async_update.side_effect = AvrIncompleteResponseError(
        "Invalid length of response XML", "test"
    )

    with pytest.raises(AvrIncompleteResponseError):
        await async_refresh_status(main)

    zone2.async_update.assert_not_awaited()


def _coordinator(
    hass: HomeAssistant, refresh_fn: AsyncMock, *, pref_disable_polling: bool = False
) -> DenonAvrDataUpdateCoordinator:
    """Build a coordinator polling every 30s through refresh_fn."""
    entry = MockConfigEntry(domain=DOMAIN, pref_disable_polling=pref_disable_polling)
    entry.add_to_hass(hass)
    main, _ = _receiver_with_zones()
    return DenonAvrDataUpdateCoordinator(
        hass, entry, main, asyncio.Lock(), "test", timedelta(seconds=30), refresh_fn
    )


async def test_a_failure_while_waiting_for_the_lock_forces_the_read(
    hass: HomeAssistant,
) -> None:
    """The skip is decided once the lock is held, not before waiting for it.

    A refresh queued behind a failing command would otherwise skip on its stale
    decision and clear the failure it was handed while waiting.
    """
    refresh_fn = AsyncMock()
    coordinator = _coordinator(hass, refresh_fn)
    await coordinator.async_refresh()

    async with coordinator.lock:
        refresh = hass.async_create_task(coordinator.async_refresh())
        await asyncio.sleep(0)
        mark_unavailable(coordinator)

    await refresh

    assert refresh_fn.await_args.kwargs["force"] is True


@pytest.mark.parametrize(
    ("peer_available", "force"),
    [
        pytest.param(True, False, id="peer_available"),
        pytest.param(False, True, id="peer_failed"),
    ],
)
async def test_a_failed_peer_forces_the_read(
    hass: HomeAssistant, peer_available: bool, force: bool
) -> None:
    """A skip must not hide the other coordinator's failure either.

    With Telnet healthy this poll would otherwise never ask the receiver the
    other coordinator just failed to reach, nor confirm that it is back.
    """
    refresh_fn = AsyncMock()
    coordinator = _coordinator(hass, refresh_fn)
    coordinator.peer = _coordinator(hass, AsyncMock())
    coordinator.peer.last_update_success = peer_available

    await coordinator.async_refresh()

    assert refresh_fn.await_args.kwargs["force"] is force


@pytest.mark.parametrize(
    ("pref_disable_polling", "polls"),
    [
        pytest.param(False, True, id="polling"),
        pytest.param(True, False, id="polling_disabled"),
    ],
)
async def test_polls_only_with_polling_enabled(
    hass: HomeAssistant, pref_disable_polling: bool, polls: bool
) -> None:
    """An interval alone does not mean the coordinator is still asking.

    _schedule_refresh() returns early on pref_disable_polling, so the other
    coordinator has to hand this one its verdict.
    """
    coordinator = _coordinator(
        hass, AsyncMock(), pref_disable_polling=pref_disable_polling
    )

    assert coordinator.polls is polls


async def test_internal_listener_does_not_start_the_poll(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The integration's own cross-coordinator wiring must not drive polling.

    async_add_listener() starts the interval for its first listener, so wiring
    the coordinators together through it would poll with every entity disabled.
    """
    refresh_fn = AsyncMock()
    coordinator = _coordinator(hass, refresh_fn)
    coordinator.async_add_internal_listener(lambda: None)

    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    refresh_fn.assert_not_awaited()

    # An actual entity subscribing is what may start it.
    coordinator.async_add_listener(lambda: None)
    freezer.tick(timedelta(seconds=31))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    refresh_fn.assert_awaited()


async def test_internal_listener_is_still_notified(hass: HomeAssistant) -> None:
    """Not polling on its own must not cost it the updates it exists for."""
    called = False

    def _record() -> None:
        nonlocal called
        called = True

    coordinator = _coordinator(hass, AsyncMock())
    coordinator.async_add_internal_listener(_record)

    coordinator.async_update_listeners()

    assert called


async def test_removing_an_internal_listener_stops_its_updates(
    hass: HomeAssistant,
) -> None:
    """Config entry unload has to be able to detach the wiring again."""
    calls = 0

    def _record() -> None:
        nonlocal calls
        calls += 1

    coordinator = _coordinator(hass, AsyncMock())
    remove = coordinator.async_add_internal_listener(_record)
    coordinator.async_update_listeners()

    remove()
    coordinator.async_update_listeners()

    assert calls == 1
