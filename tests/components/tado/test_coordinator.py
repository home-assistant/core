"""Test the Tado coordinator update interval calculation.

Add to tests/components/tado/ (new file), or fold the test into an
existing module if the maintainers prefer.
"""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.tado import DOMAIN
from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures("init_integration")
async def test_rate_limit_is_stored_in_coordinator_data(hass: HomeAssistant) -> None:
    """Test the rate limit is exposed in the coordinator data.

    _calculate_update_interval() reads self.data["rate_limit"], so it has to
    actually be filled in, otherwise the adaptive interval silently degrades
    to the static SCAN_INTERVAL.
    """
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data

    # init_integration patches PyTado's rate_limit_info to this value.
    assert coordinator.data["rate_limit"] == {"per-day": 1000, "remaining": 100}


@pytest.mark.usefixtures("init_integration")
async def test_update_interval_uses_remaining_calls(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test the update interval is derived from the remaining call budget.

    Frozen at 06:00 Berlin, so the daily reset is 6 hours (21600 s) away.
    With 6 zones the cycle costs 9 + 6 = 15 calls and a 10% buffer is kept,
    so with 100 remaining calls the interval is:

        21600 * 15 / (100 * 0.9) = 3600 s

    Before the fix remaining_calls was always 0 (the key was never written),
    which took the <= 0 branch and pinned the interval to SCAN_INTERVAL.
    """
    freezer.move_to("2026-01-15 05:00:00+00:00")  # 06:00 Europe/Berlin

    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data

    with patch.object(
        coordinator,
        "get_rate_limit",
        return_value={"per-day": "20000", "window-seconds": "86400", "remaining": "100"},
    ):
        await coordinator.async_refresh()
        await hass.async_block_till_done()

    assert coordinator.update_interval == timedelta(seconds=3600)
    assert coordinator.update_interval != timedelta(minutes=5)
