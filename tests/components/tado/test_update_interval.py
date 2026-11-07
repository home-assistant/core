"""Tests for the Tado coordinator's quota-based update interval."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from PyTado.exceptions import TadoException
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from requests import RequestException

from homeassistant.components.tado import DOMAIN
from homeassistant.components.tado.coordinator import (
    QUOTA_RETRY,
    QUOTA_WINDOW,
    SCAN_INTERVAL,
    TadoDataUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util


def _coordinator(hass: HomeAssistant) -> TadoDataUpdateCoordinator:
    return hass.config_entries.async_entries(DOMAIN)[0].runtime_data


def _calls_per_cycle(coordinator: TadoDataUpdateCoordinator) -> int:
    return 7 + len(coordinator.devices) + len(coordinator.zones)


@pytest.mark.usefixtures("init_integration")
async def test_unknown_reset_spreads_quota_over_a_full_window(
    hass: HomeAssistant,
) -> None:
    """Before the reset time is known, the quota is spread over a full window."""
    coordinator = _coordinator(hass)
    coordinator.data["rate_limit"] = {"per-day": "1000", "remaining": "500"}
    coordinator._calculate_update_interval()

    planned = QUOTA_WINDOW * _calls_per_cycle(coordinator) / (500 * 0.9)
    minimum = timedelta(minutes=5 if coordinator._is_any_zone_active else 30)
    assert coordinator.update_interval == max(planned, minimum)


@pytest.mark.usefixtures("init_integration")
async def test_reset_is_learned_when_remaining_goes_up(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A jump in the remaining calls marks the account's reset time."""
    coordinator = _coordinator(hass)
    coordinator.data["rate_limit"] = {"remaining": "40"}
    coordinator._calculate_update_interval()

    freezer.tick(timedelta(minutes=30))
    reset_seen = dt_util.utcnow()
    coordinator.data["rate_limit"] = {"remaining": "990"}
    coordinator._calculate_update_interval()
    assert coordinator._quota_reset == reset_seen + QUOTA_WINDOW

    # Shortly before the next reset the remaining calls are spent faster,
    # never later than the reset itself
    freezer.move_to(reset_seen + QUOTA_WINDOW - timedelta(hours=1))
    coordinator.data["rate_limit"] = {"remaining": "300"}
    coordinator._calculate_update_interval()
    assert coordinator.update_interval <= timedelta(hours=1, minutes=1)


@pytest.mark.usefixtures("init_integration")
async def test_reset_seconds_from_the_library_are_used(hass: HomeAssistant) -> None:
    """A seconds-to-reset value (sent by tado with a 429) sets the reset time."""
    coordinator = _coordinator(hass)
    coordinator.data["rate_limit"] = {"remaining": "800", "reset-seconds": "3600"}
    coordinator._calculate_update_interval()
    assert coordinator._time_until_reset == pytest.approx(3600, abs=1)
    assert coordinator.update_interval <= timedelta(hours=1, minutes=1)


@pytest.mark.usefixtures("init_integration")
async def test_quota_used_up_waits_for_the_reset(hass: HomeAssistant) -> None:
    """With fewer calls left than a cycle needs, the next poll waits for the reset."""
    coordinator = _coordinator(hass)
    remaining = str(_calls_per_cycle(coordinator))

    coordinator.data["rate_limit"] = {"remaining": remaining}
    coordinator._calculate_update_interval()
    assert coordinator.update_interval == QUOTA_RETRY

    coordinator.data["rate_limit"] = {"remaining": remaining, "reset-seconds": "7200"}
    coordinator._calculate_update_interval()
    assert coordinator.update_interval == timedelta(hours=2, minutes=1)


@pytest.mark.usefixtures("init_integration")
async def test_no_rate_limit_info_keeps_the_static_interval(
    hass: HomeAssistant,
) -> None:
    """Without rate-limit headers the static interval is used, as before."""
    coordinator = _coordinator(hass)
    coordinator.data["rate_limit"] = {}
    coordinator._calculate_update_interval()
    assert coordinator.update_interval == SCAN_INTERVAL


async def _tick(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delta: timedelta
) -> None:
    # One extra second: refreshes are scheduled with a sub-second offset
    freezer.tick(delta + timedelta(seconds=1))
    async_fire_time_changed(hass)
    # Scheduled coordinator refreshes run as background tasks
    await hass.async_block_till_done(wait_background_tasks=True)


@pytest.mark.parametrize(
    ("rate_limit", "retry"),
    [
        ({"remaining": "0"}, QUOTA_RETRY),
        ({"remaining": "0", "reset-seconds": "1800"}, timedelta(minutes=31)),
    ],
)
@pytest.mark.parametrize("error", [RequestException, TadoException])
@pytest.mark.usefixtures("init_integration")
async def test_rate_limited_update_waits_instead_of_polling(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    rate_limit: dict[str, str],
    retry: timedelta,
    error: type[Exception],
) -> None:
    """A failed update with the quota at zero waits for the reset (or an hour)."""
    coordinator = _coordinator(hass)
    with (
        patch.object(coordinator._tado, "get_me", side_effect=error) as get_me,
        patch.object(coordinator._tado, "rate_limit_info", return_value=rate_limit),
    ):
        await _tick(hass, freezer, coordinator.update_interval)
        assert not coordinator.last_update_success
        assert get_me.call_count == 1

        # No retry at the normal pace ...
        await _tick(hass, freezer, SCAN_INTERVAL)
        assert get_me.call_count == 1

        # ... only once the wait is over
        await _tick(hass, freezer, retry - SCAN_INTERVAL)
        assert get_me.call_count == 2


@pytest.mark.usefixtures("init_integration")
async def test_empty_me_with_quota_nearly_used_waits(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """python-tado 0.18 returns {} for an empty 429 reply; treat it as a used-up quota."""
    coordinator = _coordinator(hass)
    coordinator._last_remaining = _calls_per_cycle(coordinator)
    with patch.object(coordinator._tado, "get_me", return_value={}) as get_me:
        await _tick(hass, freezer, coordinator.update_interval)
        assert not coordinator.last_update_success
        await _tick(hass, freezer, SCAN_INTERVAL)
        assert get_me.call_count == 1
        await _tick(hass, freezer, QUOTA_RETRY - SCAN_INTERVAL)
        assert get_me.call_count == 2


@pytest.mark.usefixtures("init_integration")
async def test_cached_reset_seconds_are_not_applied_twice(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A rate-limit reading kept from an earlier 429 does not move the reset again."""
    coordinator = _coordinator(hass)
    reading = {"remaining": "0", "reset-seconds": "7200"}
    start = dt_util.utcnow()
    coordinator._learn_quota_reset(start, reading, 0)
    assert coordinator._quota_reset == start + timedelta(hours=2)

    # After the wait, a timeout leaves the same cached reading behind
    later = start + timedelta(hours=2, minutes=1)
    coordinator._learn_quota_reset(later, dict(reading), 0)
    assert coordinator._quota_reset == start + timedelta(hours=2) + QUOTA_WINDOW


@pytest.mark.usefixtures("init_integration")
async def test_known_reset_is_kept_when_the_quota_refills(
    hass: HomeAssistant,
) -> None:
    """A refill that matches the known reset time does not shift it."""
    coordinator = _coordinator(hass)
    start = dt_util.utcnow()
    coordinator._learn_quota_reset(start, {"remaining": "5", "reset-seconds": "600"}, 5)
    reset = start + timedelta(minutes=10)

    # First poll after the reset, 30 minutes late: the reset time stays on time
    after = reset + timedelta(minutes=30)
    coordinator._learn_quota_reset(after, {"remaining": "990"}, 990)
    assert coordinator._quota_reset == reset + QUOTA_WINDOW

    # A refill that the known time cannot explain re-learns it
    odd = reset + QUOTA_WINDOW / 2
    coordinator._learn_quota_reset(odd, {"remaining": "200"}, 200)
    coordinator._learn_quota_reset(
        odd + timedelta(minutes=5), {"remaining": "995"}, 995
    )
    assert coordinator._quota_reset == odd + timedelta(minutes=5) + QUOTA_WINDOW
