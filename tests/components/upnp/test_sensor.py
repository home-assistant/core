"""Tests for UPnP/IGD sensor."""

from datetime import timedelta
from unittest.mock import patch

import pytest

from homeassistant.components.upnp import UpnpDataUpdateCoordinator
from homeassistant.components.upnp.const import (
    BYTES_RECEIVED,
    BYTES_SENT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PACKETS_RECEIVED,
    PACKETS_SENT,
    ROUTER_IP,
    ROUTER_UPTIME,
    WAN_STATUS,
)
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .conftest import MockIgdDevice

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_upnp_sensors(hass: HomeAssistant, config_entry: MockConfigEntry):
    """Test normal sensors."""
    # First poll.
    b_received_state = hass.states.get("sensor.mock_name_b_received")
    b_sent_state = hass.states.get("sensor.mock_name_b_sent")
    packets_received_state = hass.states.get("sensor.mock_name_packets_received")
    packets_sent_state = hass.states.get("sensor.mock_name_packets_sent")
    external_ip_state = hass.states.get("sensor.mock_name_external_ip")
    wan_status_state = hass.states.get("sensor.mock_name_wan_status")
    assert b_received_state.state == "0"
    assert b_sent_state.state == "0"
    assert packets_received_state.state == "0"
    assert packets_sent_state.state == "0"
    assert external_ip_state.state == "8.9.10.11"
    assert wan_status_state.state == "Connected"

    # Second poll.
    mock_device: MockIgdDevice = hass.data[DOMAIN][
        config_entry.entry_id
    ].device._igd_device
    mock_device.traffic_data = {
        BYTES_RECEIVED: 10240,
        BYTES_SENT: 20480,
        PACKETS_RECEIVED: 30,
        PACKETS_SENT: 40,
    }
    mock_device.status_data = {
        WAN_STATUS: "Disconnected",
        ROUTER_UPTIME: 100,
        ROUTER_IP: "",
    }
    now = dt_util.utcnow()
    async_fire_time_changed(hass, now + timedelta(seconds=DEFAULT_SCAN_INTERVAL))
    await hass.async_block_till_done()

    b_received_state = hass.states.get("sensor.mock_name_b_received")
    b_sent_state = hass.states.get("sensor.mock_name_b_sent")
    packets_received_state = hass.states.get("sensor.mock_name_packets_received")
    packets_sent_state = hass.states.get("sensor.mock_name_packets_sent")
    external_ip_state = hass.states.get("sensor.mock_name_external_ip")
    wan_status_state = hass.states.get("sensor.mock_name_wan_status")
    assert b_received_state.state == "10240"
    assert b_sent_state.state == "20480"
    assert packets_received_state.state == "30"
    assert packets_sent_state.state == "40"
    assert external_ip_state.state == ""
    assert wan_status_state.state == "Disconnected"


async def test_derived_upnp_sensors(hass: HomeAssistant, config_entry: MockConfigEntry):
    """Test derived sensors."""
    coordinator: UpnpDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    # First poll.
    kib_s_received_state = hass.states.get("sensor.mock_name_kib_s_received")
    kib_s_sent_state = hass.states.get("sensor.mock_name_kib_s_sent")
    packets_s_received_state = hass.states.get("sensor.mock_name_packets_s_received")
    packets_s_sent_state = hass.states.get("sensor.mock_name_packets_s_sent")
    assert kib_s_received_state.state == "unknown"
    assert kib_s_sent_state.state == "unknown"
    assert packets_s_received_state.state == "unknown"
    assert packets_s_sent_state.state == "unknown"

    # Second poll.
    now = dt_util.utcnow()
    with patch(
        "homeassistant.components.upnp.device.utcnow",
        return_value=now + timedelta(seconds=DEFAULT_SCAN_INTERVAL),
    ):
        mock_device: MockIgdDevice = coordinator.device._igd_device
        mock_device.traffic_data = {
            BYTES_RECEIVED: int(10240 * DEFAULT_SCAN_INTERVAL),
            BYTES_SENT: int(20480 * DEFAULT_SCAN_INTERVAL),
            PACKETS_RECEIVED: int(30 * DEFAULT_SCAN_INTERVAL),
            PACKETS_SENT: int(40 * DEFAULT_SCAN_INTERVAL),
        }
        async_fire_time_changed(hass, now + timedelta(seconds=DEFAULT_SCAN_INTERVAL))
        await hass.async_block_till_done()

        kib_s_received_state = hass.states.get("sensor.mock_name_kib_s_received")
        kib_s_sent_state = hass.states.get("sensor.mock_name_kib_s_sent")
        packets_s_received_state = hass.states.get(
            "sensor.mock_name_packets_s_received"
        )
        packets_s_sent_state = hass.states.get("sensor.mock_name_packets_s_sent")
        assert float(kib_s_received_state.state) == pytest.approx(10.0, rel=0.1)
        assert float(kib_s_sent_state.state) == pytest.approx(20.0, rel=0.1)
        assert float(packets_s_received_state.state) == pytest.approx(30.0, rel=0.1)
        assert float(packets_s_sent_state.state) == pytest.approx(40.0, rel=0.1)
