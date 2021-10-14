"""Tests for UPnP/IGD binary_sensor."""

from unittest.mock import AsyncMock

from homeassistant.components.upnp.const import (
    ROUTER_IP,
    ROUTER_UPTIME,
    UPDATE_INTERVAL,
    WAN_STATUS,
)
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .conftest import MockDevice

from tests.common import async_fire_time_changed


async def test_upnp_binary_sensors(
    hass: HomeAssistant, initialed_integration: MockDevice
):
    """Test normal sensors."""
    mock_device = initialed_integration

    # First poll.
    wan_status_state = hass.states.get("binary_sensor.mock_name_wan_status")
    assert wan_status_state.state == "on"

    # Second poll.
    mock_device.async_get_status = AsyncMock(
        return_value={
            WAN_STATUS: "Disconnected",
            ROUTER_UPTIME: 100,
            ROUTER_IP: "",
        }
    )
    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    wan_status_state = hass.states.get("binary_sensor.mock_name_wan_status")
    assert wan_status_state.state == "off"
