"""Tests for the Smart Meter B Route Coordinator."""

from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
from momonga import MomongaError

from homeassistant.components.smart_meter_b_route.const import DEFAULT_SCAN_INTERVAL
from homeassistant.components.smart_meter_b_route.coordinator import (
    BRouteData,
    BRouteUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import async_fire_time_changed


async def test_broute_update_coordinator(
    hass: HomeAssistant, mock_momonga: Mock, freezer: FrozenDateTimeFactory
) -> None:
    """Test the BRouteUpdateCoordinator."""
    coordinator = BRouteUpdateCoordinator(hass, "device", "id", "password")

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.data == BRouteData(
        instantaneous_current_r_phase=1,
        instantaneous_current_t_phase=2,
        instantaneous_power=3,
        total_consumption=4,
    )

    mock_momonga.return_value.get_instantaneous_current.side_effect = MomongaError

    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert coordinator.last_update_success is False
    assert coordinator.last_exception is not None
    assert isinstance(coordinator.last_exception, UpdateFailed)
