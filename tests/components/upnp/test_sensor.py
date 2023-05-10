"""Tests for UPnP/IGD sensor."""

from datetime import datetime, timedelta

from async_upnp_client.profiles.igd import IgdDevice, IgdState, StatusInfo

from homeassistant.components.upnp.const import DEFAULT_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_upnp_sensors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test sensors."""
    # First poll.
    assert hass.states.get("sensor.mock_name_b_received").state == "0"
    assert hass.states.get("sensor.mock_name_b_sent").state == "0"
    assert hass.states.get("sensor.mock_name_packets_received").state == "0"
    assert hass.states.get("sensor.mock_name_packets_sent").state == "0"
    assert hass.states.get("sensor.mock_name_external_ip").state == "8.9.10.11"
    assert hass.states.get("sensor.mock_name_wan_status").state == "Connected"
    assert hass.states.get("sensor.mock_name_kib_s_received").state == "unknown"
    assert hass.states.get("sensor.mock_name_kib_s_sent").state == "unknown"
    assert hass.states.get("sensor.mock_name_packets_s_received").state == "unknown"
    assert hass.states.get("sensor.mock_name_packets_s_sent").state == "unknown"

    # Second poll.
    mock_igd_device: IgdDevice = mock_config_entry.igd_device
    mock_igd_device.async_get_traffic_and_status_data.return_value = IgdState(
        timestamp=datetime.now(),
        bytes_received=10240,
        bytes_sent=20480,
        packets_received=30,
        packets_sent=40,
        status_info=StatusInfo(
            "Disconnected",
            "",
            40,
        ),
        external_ip_address="",
        kibibytes_per_sec_received=10.0,
        kibibytes_per_sec_sent=20.0,
        packets_per_sec_received=30.0,
        packets_per_sec_sent=40.0,
    )

    now = dt_util.utcnow()
    async_fire_time_changed(hass, now + timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    await hass.async_block_till_done()

    assert hass.states.get("sensor.mock_name_b_received").state == "10240"
    assert hass.states.get("sensor.mock_name_b_sent").state == "20480"
    assert hass.states.get("sensor.mock_name_packets_received").state == "30"
    assert hass.states.get("sensor.mock_name_packets_sent").state == "40"
    assert hass.states.get("sensor.mock_name_external_ip").state == ""
    assert hass.states.get("sensor.mock_name_wan_status").state == "Disconnected"
    assert hass.states.get("sensor.mock_name_kib_s_received").state == "10.0"
    assert hass.states.get("sensor.mock_name_kib_s_sent").state == "20.0"
    assert hass.states.get("sensor.mock_name_packets_s_received").state == "30.0"
    assert hass.states.get("sensor.mock_name_packets_s_sent").state == "40.0"
