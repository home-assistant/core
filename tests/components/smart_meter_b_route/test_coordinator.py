"""Tests for the Smart Meter B Route Coordinator."""

from unittest.mock import Mock, patch

from momonga import MomongaError

from homeassistant.components.smart_meter_b_route.const import (
    ATTR_API_INSTANTANEOUS_CURRENT_R_PHASE,
    ATTR_API_INSTANTANEOUS_CURRENT_T_PHASE,
    ATTR_API_INSTANTANEOUS_POWER,
    ATTR_API_TOTAL_CONSUMPTION,
)
from homeassistant.components.smart_meter_b_route.coordinator import (
    BRouteUpdateCoordinator,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed


async def test_broute_update_coordinator(
    hass: HomeAssistant, mock_momonga: Mock
) -> None:
    """Test the BRouteUpdateCoordinator."""
    coordinator = BRouteUpdateCoordinator(hass, "device", "id", "password")

    await coordinator.async_refresh()

    assert coordinator.data == {
        ATTR_API_INSTANTANEOUS_CURRENT_R_PHASE: 1,
        ATTR_API_INSTANTANEOUS_CURRENT_T_PHASE: 2,
        ATTR_API_INSTANTANEOUS_POWER: 3,
        ATTR_API_TOTAL_CONSUMPTION: 4,
    }

    with patch.object(
        mock_momonga, "get_instantaneous_current", side_effect=MomongaError
    ):
        await coordinator.async_refresh()

        assert coordinator.last_update_success is False
        assert coordinator.last_exception is not None
        assert isinstance(coordinator.last_exception, UpdateFailed)
