"""Tests for UPnP/IGD binary_sensor."""

from datetime import timedelta

from async_upnp_client.profiles.igd import StatusInfo

from homeassistant.components.upnp.const import DEFAULT_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_upnp_binary_sensors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
):
    """Test normal sensors."""
    # First poll.
    wan_status_state = hass.states.get("binary_sensor.mock_name_wan_status")
    assert wan_status_state.state == "on"

    # Second poll.
    mock_igd_device = mock_config_entry.igd_device
    mock_igd_device.async_get_status_info.return_value = StatusInfo(
        "Disconnected",
        "",
        40,
    )

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=DEFAULT_SCAN_INTERVAL)
    )
    await hass.async_block_till_done()

    wan_status_state = hass.states.get("binary_sensor.mock_name_wan_status")
    assert wan_status_state.state == "off"
