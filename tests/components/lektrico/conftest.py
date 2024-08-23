"""Fixtures for Lektrico Charging Station integration tests."""

from ipaddress import ip_address
from typing import Any
from unittest.mock import AsyncMock, patch

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


def _mocked_device_info() -> dict[str, Any]:
    return {
        "charger_state": "Available",
        "charging_time": 0,
        "instant_power": 0,
        "session_energy": 0.0,
        "temperature": 34.5,
        "total_charged_energy": 0,
        "install_current": 6,
        "current_limit_reason": "Installation current",
        "voltage_l1": 220.0,
        "current_l1": 0.0,
    }


@pytest.fixture
def mock_device():
    """Patch Device class."""
    with patch("homeassistant.components.lektrico.config_flow.Device") as MockDevice:
        # Mock metodele specifice dacă ai nevoie de ele
        MockDevice.return_value.device_config = AsyncMock(
            return_value=_mocked_device_config()
        )
        MockDevice.return_value.device_info = AsyncMock(
            return_value=_mocked_device_info()
        )

        MockDevice.return_value.send_charge_start = AsyncMock(
            return_value={"status": "success"}
        )
        MockDevice.return_value.send_charge_stop = AsyncMock(
            return_value={"status": "success"}
        )
        MockDevice.return_value.send_reset = AsyncMock(
            return_value={"status": "success"}
        )
        MockDevice.return_value.set_auth = AsyncMock(return_value={"status": "success"})
        MockDevice.return_value.set_led_max_brightness = AsyncMock(
            return_value={"status": "success"}
        )
        MockDevice.return_value.set_dynamic_current = AsyncMock(
            return_value={"status": "success"}
        )
        MockDevice.return_value.set_user_current = AsyncMock(
            return_value={"status": "success"}
        )
        MockDevice.return_value.set_load_balancing_mode = AsyncMock(
            return_value={"status": "success"}
        )
        MockDevice.return_value.set_charger_locked = AsyncMock(return_value=True)
        MockDevice.return_value.set_relay_mode = AsyncMock(return_value=True)

        yield MockDevice


@pytest.fixture
def mock_setup_entry():
    """Mock setup entry."""
    with patch(
        "homeassistant.components.lektrico.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
