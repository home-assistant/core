"""Fixtures for Lektrico Charging Station integration tests."""

from ipaddress import ip_address
from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.components.zeroconf import ZeroconfServiceInfo

MOCKED_DEVICE_IP_ADDRESS = "192.168.100.10"
MOCKED_DEVICE_SERIAL_NUMBER = "500006"
MOCKED_DEVICE_TYPE = "1p7k"
MOCKED_DEVICE_BOARD_REV = "B"

MOCKED_DEVICE_ZC_NAME = "Lektrico-1p7k-500006._http._tcp"
MOCKED_DEVICE_ZC_TYPE = "_http._tcp.local."
MOCKED_DEVICE_ZEROCONF_DATA = ZeroconfServiceInfo(
    ip_address=ip_address(MOCKED_DEVICE_IP_ADDRESS),
    ip_addresses=[ip_address(MOCKED_DEVICE_IP_ADDRESS)],
    hostname=f"{MOCKED_DEVICE_ZC_NAME.lower()}.local.",
    port=80,
    type=MOCKED_DEVICE_ZC_TYPE,
    name=MOCKED_DEVICE_ZC_NAME,
    properties={
        "id": "1p7k_500006",
        "fw_id": "20230109-124642/v1.22-36-g56a3edd-develop-dirty",
    },
)


def _mocked_device_config() -> dict[str, Any]:
    return {
        "type": MOCKED_DEVICE_TYPE,
        "serial_number": MOCKED_DEVICE_SERIAL_NUMBER,
        "board_revision": MOCKED_DEVICE_BOARD_REV,
    }


@pytest.fixture
def mock_device_config():
    """Override device_config() for 1P7K or 3P7K devices."""
    with patch(
        "homeassistant.components.lektrico.config_flow.Device.device_config",
        return_value=_mocked_device_config(),
    ) as mocked_device_config:
        yield mocked_device_config


@pytest.fixture
def mock_setup_entry():
    """Mock setup entry."""
    with patch(
        "homeassistant.components.lektrico.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
