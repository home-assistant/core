"""Tests for UPnP/IGD sensor."""

from datetime import timedelta
from unittest.mock import patch

from async_upnp_client.profiles.igd import StatusInfo
import pytest

from homeassistant.components.upnp.const import DEFAULT_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_upnp_sensors(hass: HomeAssistant, mock_config_entry: MockConfigEntry):
    """Test normal sensors."""
    # First poll.
    assert hass.states.get("sensor.mock_name_b_received").state == "0"
    assert hass.states.get("sensor.mock_name_b_sent").state == "0"
    assert hass.states.get("sensor.mock_name_packets_received").state == "0"
    assert hass.states.get("sensor.mock_name_packets_sent").state == "0"
    assert hass.states.get("sensor.mock_name_external_ip").state == "8.9.10.11"
    assert hass.states.get("sensor.mock_name_wan_status").state == "Connected"

    # Second poll.
    mock_igd_device = mock_config_entry.igd_device
    mock_igd_device.async_get_total_bytes_received.return_value = 10240
    mock_igd_device.async_get_total_bytes_sent.return_value = 20480
    mock_igd_device.async_get_total_packets_received.return_value = 30
    mock_igd_device.async_get_total_packets_sent.return_value = 40
    mock_igd_device.async_get_status_info.return_value = StatusInfo(
        "Disconnected",
        "",
        40,
    )
    mock_igd_device.async_get_external_ip_address.return_value = ""

    now = dt_util.utcnow()
    async_fire_time_changed(hass, now + timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    await hass.async_block_till_done()

    assert hass.states.get("sensor.mock_name_b_received").state == "10240"
    assert hass.states.get("sensor.mock_name_b_sent").state == "20480"
    assert hass.states.get("sensor.mock_name_packets_received").state == "30"
    assert hass.states.get("sensor.mock_name_packets_sent").state == "40"
    assert hass.states.get("sensor.mock_name_external_ip").state == ""
    assert hass.states.get("sensor.mock_name_wan_status").state == "Disconnected"


async def test_derived_upnp_sensors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
):
    """Test derived sensors."""
    # First poll.
    assert hass.states.get("sensor.mock_name_kib_s_received").state == "unknown"
    assert hass.states.get("sensor.mock_name_kib_s_sent").state == "unknown"
    assert hass.states.get("sensor.mock_name_packets_s_received").state == "unknown"
    assert hass.states.get("sensor.mock_name_packets_s_sent").state == "unknown"

    # Second poll.
    mock_igd_device = mock_config_entry.igd_device
    mock_igd_device.async_get_total_bytes_received.return_value = int(
        10240 * DEFAULT_SCAN_INTERVAL
    )
    mock_igd_device.async_get_total_bytes_sent.return_value = int(
        20480 * DEFAULT_SCAN_INTERVAL
    )
    mock_igd_device.async_get_total_packets_received.return_value = int(
        30 * DEFAULT_SCAN_INTERVAL
    )
    mock_igd_device.async_get_total_packets_sent.return_value = int(
        40 * DEFAULT_SCAN_INTERVAL
    )

    now = dt_util.utcnow()
    with patch(
        "homeassistant.components.upnp.device.utcnow",
        return_value=now + timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    ):
        async_fire_time_changed(hass, now + timedelta(seconds=DEFAULT_SCAN_INTERVAL))
        await hass.async_block_till_done()

        assert float(
            hass.states.get("sensor.mock_name_kib_s_received").state
        ) == pytest.approx(10.0, rel=0.1)
        assert float(
            hass.states.get("sensor.mock_name_kib_s_sent").state
        ) == pytest.approx(20.0, rel=0.1)
        assert float(
            hass.states.get("sensor.mock_name_packets_s_received").state
        ) == pytest.approx(30.0, rel=0.1)
        assert float(
            hass.states.get("sensor.mock_name_packets_s_sent").state
        ) == pytest.approx(40.0, rel=0.1)
