"""Fixtures for Lektrico Charging Station integration tests."""

from collections.abc import Generator
from ipaddress import ip_address
import json
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.lektrico.const import DOMAIN
from homeassistant.const import (
    ATTR_HW_VERSION,
    ATTR_SERIAL_NUMBER,
    CONF_HOST,
    CONF_TYPE,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry, load_fixture

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


@pytest.fixture
def mock_device() -> Generator[AsyncMock]:
    """Mock a Lektrico device."""
    with (
        patch(
            "homeassistant.components.lektrico.Device",
            autospec=True,
        ) as mock_device,
        patch(
            "homeassistant.components.lektrico.config_flow.Device",
            new=mock_device,
        ),
        patch(
            "homeassistant.components.lektrico.coordinator.Device",
            new=mock_device,
        ),
    ):
        device = mock_device.return_value

        device.device_config.return_value = json.loads(
            load_fixture("get_config.json", DOMAIN)
        )
        device.device_info.return_value = json.loads(
            load_fixture("get_info.json", DOMAIN)
        )

        yield device


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setup entry."""
    with patch(
        "homeassistant.components.lektrico.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: MOCKED_DEVICE_IP_ADDRESS,
            CONF_TYPE: MOCKED_DEVICE_TYPE,
            ATTR_SERIAL_NUMBER: MOCKED_DEVICE_SERIAL_NUMBER,
            ATTR_HW_VERSION: "B",
        },
        unique_id=MOCKED_DEVICE_SERIAL_NUMBER,
    )
