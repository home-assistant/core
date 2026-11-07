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
from homeassistant.helpers.update_coordinator import UpdateFailed
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
    # Below the setup polls' 100, so this is not a refill that reveals the reset
    coordinator.data["rate_limit"] = {"per-day": "1000", "remaining": "80"}
    coordinator._calculate_update_interval()
    assert coordinator._quota_reset is None

    planned = QUOTA_WINDOW * _calls_per_cycle(coordinator) / (80 * 0.9)
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
async def test_empty_reply_waits_and_keeps_zones_and_devices(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """python-tado 0.18 returns {} for an empty 429 reply; wait, keep the lists."""
    coordinator = _coordinator(hass)
    zones, devices = coordinator.zones, coordinator.devices
    with (
        patch.object(coordinator._tado, "get_me", return_value={}) as get_me,
        patch.object(coordinator._tado, "get_zones", return_value={}),
        patch.object(coordinator._tado, "get_devices", return_value={}),
    ):
        await _tick(hass, freezer, coordinator.update_interval)
        assert not coordinator.last_update_success
        assert coordinator.zones == zones
        assert coordinator.devices == devices

        await _tick(hass, freezer, SCAN_INTERVAL)
        assert get_me.call_count == 1
        await _tick(hass, freezer, QUOTA_RETRY - SCAN_INTERVAL)
        assert get_me.call_count == 2


@pytest.mark.usefixtures("init_integration")
async def test_reply_without_homes_is_a_normal_failure(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A /me reply without homes fails the update without a quota wait."""
    coordinator = _coordinator(hass)
    with patch.object(coordinator._tado, "get_me", return_value={"id": 1}) as get_me:
        await _tick(hass, freezer, coordinator.update_interval)
        assert not coordinator.last_update_success
        await _tick(hass, freezer, coordinator.update_interval)
        assert get_me.call_count == 2


@pytest.mark.parametrize(
    "method",
    ["get_devices", "get_zone_states", "get_zone_overlay_default", "get_home_state"],
)
@pytest.mark.usefixtures("init_integration")
async def test_rate_limit_in_a_later_stage_waits(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, method: str
) -> None:
    """A 429 after the preload gets the same quota back-off in every stage."""
    coordinator = _coordinator(hass)
    side_effect: object = TadoException
    if method == "get_devices":
        # The preload asks for the devices too; fail only the second call
        side_effect = [coordinator.devices, TadoException]
    with (
        patch.object(coordinator._tado, method, side_effect=side_effect) as failing,
        patch.object(
            coordinator._tado,
            "rate_limit_info",
            return_value={"remaining": "0", "reset-seconds": "1800"},
        ),
    ):
        await _tick(hass, freezer, coordinator.update_interval)
        assert not coordinator.last_update_success
        calls = failing.call_count

        await _tick(hass, freezer, SCAN_INTERVAL)
        assert failing.call_count == calls


@pytest.mark.usefixtures("init_integration")
async def test_rate_limit_when_refreshing_one_zone(hass: HomeAssistant) -> None:
    """The single-zone refresh after a change reports the quota wait too."""
    coordinator = _coordinator(hass)
    with (
        patch.object(coordinator._tado, "get_zone_state", side_effect=TadoException),
        patch.object(
            coordinator._tado,
            "rate_limit_info",
            return_value={"remaining": "0", "reset-seconds": "1800"},
        ),
        pytest.raises(UpdateFailed) as exc_info,
    ):
        await coordinator._update_zone(1)
    assert exc_info.value.retry_after == timedelta(minutes=31).total_seconds()


@pytest.mark.usefixtures("init_integration")
async def test_timeout_after_the_reset_does_not_add_a_day(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """A cached zero-quota reading after the reset must not push the next try a day out."""
    coordinator = _coordinator(hass)
    reading = {"remaining": "0", "reset-seconds": "1800"}
    with (
        patch.object(
            coordinator._tado, "get_me", side_effect=RequestException
        ) as get_me,
        patch.object(coordinator._tado, "rate_limit_info", return_value=reading),
    ):
        # The 429: wait for the reset
        await _tick(hass, freezer, coordinator.update_interval)
        assert get_me.call_count == 1
        # After the reset a timeout leaves the same cached reading behind
        await _tick(hass, freezer, timedelta(minutes=31))
        assert get_me.call_count == 2
        # ... which is a normal failure: the next try comes at the usual pace
        await _tick(hass, freezer, coordinator.update_interval)
        assert get_me.call_count == 3


@pytest.mark.usefixtures("init_integration")
async def test_reset_due_now_is_not_moved_to_tomorrow(hass: HomeAssistant) -> None:
    """reset-seconds 0 means the quota resets now: retry shortly, not in a day."""
    coordinator = _coordinator(hass)
    now = dt_util.utcnow()
    coordinator._learn_quota_reset(now, {"remaining": "0", "reset-seconds": "0"}, 0)
    assert coordinator._quota_reset == now
    assert coordinator._wait_for_quota(now) == timedelta(minutes=1)


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
