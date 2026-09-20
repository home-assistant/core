"""The tests for denonavr's coordinator module-level refresh functions."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock

from denonavr.exceptions import AvrCommandError
from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.denonavr.const import DOMAIN
from homeassistant.components.denonavr.coordinator import (
    DenonAvrDataUpdateCoordinator,
    async_refresh_audyssey,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_fire_time_changed


def _receiver_with_zones() -> tuple[MagicMock, MagicMock]:
    """Build a fake receiver with a Main and a Zone2 zone."""
    main = MagicMock()
    main.name = "Main Receiver"
    main.telnet_connected = False
    main.telnet_healthy = False
    main.async_update_audyssey = AsyncMock()
    zone2 = MagicMock()
    zone2.zone = "Zone2"
    zone2.async_update_audyssey = AsyncMock()
    main.zones = {"Main": main, "Zone2": zone2}
    return main, zone2


async def test_async_refresh_audyssey_refreshes_every_zone() -> None:
    """Each zone is its own object with its own cached Audyssey state.

    denonavr's async_update_audyssey() only updates the zone it's
    called on - a multi-zone receiver's Zone2/Zone3 media players would
    otherwise never get their own Audyssey data refreshed at all.
    """
    main, zone2 = _receiver_with_zones()

    await async_refresh_audyssey(main)

    main.async_update_audyssey.assert_awaited_once()
    zone2.async_update_audyssey.assert_awaited_once()


async def test_async_refresh_audyssey_skips_every_zone_when_telnet_healthy() -> None:
    """The Telnet-healthy skip applies to every zone at once, checked only once."""
    main, zone2 = _receiver_with_zones()
    main.telnet_connected = True
    main.telnet_healthy = True

    await async_refresh_audyssey(main)

    main.async_update_audyssey.assert_not_awaited()
    zone2.async_update_audyssey.assert_not_awaited()


async def test_async_refresh_audyssey_continues_after_one_zones_command_error() -> None:
    """A rejected/unsupported command in one zone doesn't abort the others.

    Matches async_refresh_status's own per-zone resilience - not every
    zone need support Audyssey identically, and one zone's
    AvrCommandError shouldn't leave every other zone's data unrefreshed.
    """
    main, zone2 = _receiver_with_zones()
    main.async_update_audyssey = AsyncMock(
        side_effect=AvrCommandError("not supported", "GetAudyssey")
    )

    await async_refresh_audyssey(main)

    zone2.async_update_audyssey.assert_awaited_once()


def _coordinator(
    hass: HomeAssistant, refresh_fn: AsyncMock
) -> DenonAvrDataUpdateCoordinator:
    """Build a coordinator polling every 30s through refresh_fn."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.add_to_hass(hass)
    main, _ = _receiver_with_zones()
    return DenonAvrDataUpdateCoordinator(
        hass, entry, main, asyncio.Lock(), "test", timedelta(seconds=30), refresh_fn
    )


async def test_internal_listener_does_not_start_the_poll(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """The integration's own cross-coordinator wiring must not drive polling.

    async_add_listener() starts the interval for its first listener, so
    wiring the coordinators together through it would keep an expensive
    poll running even with every entity it backs disabled.
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
