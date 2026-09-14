"""The tests for denonavr's coordinator module-level refresh functions."""

from unittest.mock import AsyncMock, MagicMock

from denonavr.exceptions import AvrCommandError

from homeassistant.components.denonavr.coordinator import async_refresh_audyssey


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
