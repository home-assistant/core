"""Tests for the Tado coordinator's quota-based update interval."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
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


@pytest.mark.usefixtures("init_integration")
async def test_rate_limited_update_does_not_poll_every_five_minutes(
    hass: HomeAssistant,
) -> None:
    """A failed update with the quota at zero backs off instead of retrying soon."""
    coordinator = _coordinator(hass)
    with (
        patch.object(coordinator._tado, "get_me", side_effect=RequestException),
        patch.object(
            coordinator._tado, "rate_limit_info", return_value={"remaining": "0"}
        ),
    ):
        await coordinator.async_refresh()
    assert not coordinator.last_update_success
    assert coordinator.update_interval == QUOTA_RETRY

    with (
        patch.object(coordinator._tado, "get_me", side_effect=RequestException),
        patch.object(
            coordinator._tado,
            "rate_limit_info",
            return_value={"remaining": "0", "reset-seconds": "1800"},
        ),
    ):
        await coordinator.async_refresh()
    assert coordinator.update_interval == timedelta(minutes=31)
