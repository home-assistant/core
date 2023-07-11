"""Tests for UPnP/IGD binary_sensor."""

from datetime import datetime, timedelta

from async_upnp_client.profiles.igd import IgdDevice, IgdState, StatusInfo

from homeassistant.components.upnp.const import DEFAULT_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_upnp_binary_sensors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test normal sensors."""
    # First poll.
    wan_status_state = hass.states.get("binary_sensor.mock_name_wan_status")
    assert wan_status_state.state == "on"

    # Second poll.
    mock_igd_device: IgdDevice = mock_config_entry.igd_device
    mock_igd_device.async_get_traffic_and_status_data.return_value = IgdState(
        timestamp=datetime.now(),
        bytes_received=0,
        bytes_sent=0,
        packets_received=0,
        packets_sent=0,
        status_info=StatusInfo(
            "Disconnected",
            "",
            40,
        ),
        external_ip_address="8.9.10.11",
        kibibytes_per_sec_received=None,
        kibibytes_per_sec_sent=None,
        packets_per_sec_received=None,
        packets_per_sec_sent=None,
    )

    async_fire_time_changed(
        hass, dt_util.utcnow() + timedelta(seconds=DEFAULT_SCAN_INTERVAL)
    )
    await hass.async_block_till_done()

    wan_status_state = hass.states.get("binary_sensor.mock_name_wan_status")
    assert wan_status_state.state == "off"
