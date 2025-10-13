"""Common fixtures for the Dali Center tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.sunricher_dali_center.const import (
    CONF_CHANNEL_TOTAL,
    CONF_SN,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SN: "6A242121110E",
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1883,
            CONF_NAME: "Test Gateway",
            CONF_USERNAME: "gateway_user",
            CONF_PASSWORD: "gateway_pass",
            CONF_CHANNEL_TOTAL: [1, 2],
            CONF_SSL: False,
        },
        unique_id="6A242121110E",
        title="Test Gateway",
    )


@pytest.fixture
def mock_devices(mock_dali_gateway: MagicMock) -> Generator[list[MagicMock]]:
    """Return mocked Device objects."""
    with patch(
        "homeassistant.components.sunricher_dali_center.light.Device"
    ) as mock_device_class:
        device1 = MagicMock()
        device1.dev_id = "01010000026A242121110E"
        device1.unique_id = "01010000026A242121110E"
        device1.status = "online"
        device1.dev_type = "0101"
        device1.name = "Dimmer 0000-02"
        device1.model = "DALI DT6 Dimmable Driver"
        device1.gw_sn = "6A242121110E"
        device1.color_mode = "brightness"
        device1.turn_on = MagicMock()
        device1.turn_off = MagicMock()
        device1.read_status = MagicMock()

        device2 = MagicMock()
        device2.dev_id = "01020000036A242121110E"
        device2.unique_id = "01020000036A242121110E"
        device2.status = "online"
        device2.dev_type = "0102"
        device2.name = "CCT 0000-03"
        device2.model = "DALI DT8 Tc Dimmable Driver"
        device2.gw_sn = "6A242121110E"
        device2.color_mode = "color_temp"
        device2.turn_on = MagicMock()
        device2.turn_off = MagicMock()
        device2.read_status = MagicMock()

        # Add devices with different color modes for better coverage
        device3 = MagicMock()
        device3.dev_id = "01030000046A242121110E"
        device3.unique_id = "01030000046A242121110E"
        device3.status = "online"
        device3.dev_type = "0103"
        device3.name = "HS Color Light"
        device3.model = "DALI HS Color Driver"
        device3.gw_sn = "6A242121110E"
        device3.color_mode = "hs"
        device3.turn_on = MagicMock()
        device3.turn_off = MagicMock()
        device3.read_status = MagicMock()

        device4 = MagicMock()
        device4.dev_id = "01040000056A242121110E"
        device4.unique_id = "01040000056A242121110E"
        device4.status = "online"
        device4.dev_type = "0104"
        device4.name = "RGBW Light"
        device4.model = "DALI RGBW Driver"
        device4.gw_sn = "6A242121110E"
        device4.color_mode = "rgbw"
        device4.turn_on = MagicMock()
        device4.turn_off = MagicMock()
        device4.read_status = MagicMock()

        # Add a duplicate device to test the continue logic (line 58)
        device_duplicate = MagicMock()
        device_duplicate.dev_id = "01010000026A242121110E"  # Same as device1
        device_duplicate.unique_id = "01010000026A242121110E"
        device_duplicate.status = "online"
        device_duplicate.dev_type = "0101"
        device_duplicate.name = "Duplicate Dimmer"
        device_duplicate.model = "DALI DT6 Dimmable Driver"
        device_duplicate.gw_sn = "6A242121110E"
        device_duplicate.color_mode = "brightness"
        device_duplicate.turn_on = MagicMock()
        device_duplicate.turn_off = MagicMock()
        device_duplicate.read_status = MagicMock()

        devices = [device1, device2, device3, device4, device_duplicate]
        mock_device_class.side_effect = devices

        mock_dali_gateway.discover_devices = AsyncMock(
            return_value=[{"dev_id": device.dev_id} for device in devices]
        )

        yield devices


@pytest.fixture
def mock_discovery() -> Generator[MagicMock]:
    """Mock DaliGatewayDiscovery."""
    with patch(
        "homeassistant.components.sunricher_dali_center.config_flow.DaliGatewayDiscovery"
    ) as mock_discovery_class:
        mock_discovery = mock_discovery_class.return_value
        mock_discovery.discover_gateways = AsyncMock()
        yield mock_discovery


@pytest.fixture
def mock_dali_gateway() -> Generator[MagicMock]:
    """Return a mocked DaliGateway."""
    with patch(
        "homeassistant.components.sunricher_dali_center.DaliGateway", autospec=True
    ) as mock_gateway_class:
        mock_gateway = mock_gateway_class.return_value
        mock_gateway.gw_sn = "6A242121110E"
        mock_gateway.name = "Test Gateway"
        mock_gateway.connect = AsyncMock()
        mock_gateway.disconnect = AsyncMock()
        yield mock_gateway


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sunricher_dali_center.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
