"""Test configuration for the Bbox component."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.device_tracker import DOMAIN as DEVICE_TRACKER_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import CONF_HOST, CONF_MONITORED_VARIABLES, CONF_NAME


@pytest.fixture
def mock_bbox_api() -> Generator[MagicMock]:
    """Mock the pybbox API."""
    with (
        patch(
            "homeassistant.components.bbox.device_tracker.pybbox.Bbox"
        ) as mock_bbox_client,
        patch(
            "homeassistant.components.bbox.sensor.pybbox.Bbox"
        ) as mock_bbox_client_sensor,
    ):
        mock_bbox = MagicMock()
        mock_bbox_client.return_value = mock_bbox
        mock_bbox_client_sensor.return_value = mock_bbox

        mock_bbox.get_all_connected_devices.return_value = [
            {
                "macaddress": "aa:bb:cc:dd:ee:ff",
                "hostname": "test_device",
                "ipaddress": "192.168.1.100",
                "active": 1,
            },
            {
                "macaddress": "ff:ee:dd:cc:bb:aa",
                "hostname": "another_device",
                "ipaddress": "192.168.1.101",
                "active": 1,
            },
            {
                "macaddress": "11:22:33:44:55:66",
                "hostname": "inactive_device",
                "ipaddress": "192.168.1.102",
                "active": 0,
            },
        ]

        mock_bbox.get_ip_stats.return_value = {
            "rx": {
                "maxBandwidth": 100000000,  # 100 Mbps
                "bandwidth": 50000000,  # 50 Mbps
            },
            "tx": {
                "maxBandwidth": 50000000,  # 50 Mbps
                "bandwidth": 25000000,  # 25 Mbps
            },
        }

        mock_bbox.get_bbox_info.return_value = {
            "device": {
                "uptime": 3600,  # 1 hour
                "numberofboots": 5,
            }
        }

        yield mock_bbox


@pytest.fixture
def device_tracker_config() -> dict:
    """Return device tracker configuration."""
    return {DEVICE_TRACKER_DOMAIN: {"platform": "bbox", CONF_HOST: "192.168.1.254"}}


@pytest.fixture
def sensor_config() -> dict:
    """Return sensor configuration."""
    return {
        SENSOR_DOMAIN: {
            "platform": "bbox",
            CONF_MONITORED_VARIABLES: [
                "down_max_bandwidth",
                "up_max_bandwidth",
                "current_down_bandwidth",
                "current_up_bandwidth",
                "number_of_reboots",
                "uptime",
            ],
            CONF_NAME: "Test Bbox",
        }
    }
