"""Common fixtures for the Dali Center tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.sunricher_dali_center.const import (
    CONF_SERIAL_NUMBER,
    DOMAIN,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_SERIAL_NUMBER: "6A242121110E",
            CONF_HOST: "192.168.1.100",
            CONF_PORT: 1883,
            CONF_NAME: "Test Gateway",
            CONF_USERNAME: "gateway_user",
            CONF_PASSWORD: "gateway_pass",
        },
        unique_id="6A242121110E",
        title="Test Gateway",
    )


def _create_mock_device(
    dev_id: str,
    dev_type: str,
    name: str,
    model: str,
    color_mode: str,
    gw_sn: str = "6A242121110E",
) -> MagicMock:
    """Create a mock device with standard attributes."""
    device = MagicMock()
    device.dev_id = dev_id
    device.unique_id = dev_id
    device.status = "online"
    device.dev_type = dev_type
    device.name = name
    device.model = model
    device.gw_sn = gw_sn
    device.color_mode = color_mode
    device.turn_on = MagicMock()
    device.turn_off = MagicMock()
    device.read_status = MagicMock()
    return device


@pytest.fixture
def mock_devices() -> list[MagicMock]:
    """Return mocked Device objects."""
    return [
        _create_mock_device(
            "01010000026A242121110E",
            "0101",
            "Dimmer 0000-02",
            "DALI DT6 Dimmable Driver",
            "brightness",
        ),
        _create_mock_device(
            "01020000036A242121110E",
            "0102",
            "CCT 0000-03",
            "DALI DT8 Tc Dimmable Driver",
            "color_temp",
        ),
        _create_mock_device(
            "01030000046A242121110E",
            "0103",
            "HS Color Light",
            "DALI HS Color Driver",
            "hs",
        ),
        _create_mock_device(
            "01040000056A242121110E",
            "0104",
            "RGBW Light",
            "DALI RGBW Driver",
            "rgbw",
        ),
        _create_mock_device(
            "01010000026A242121110E",
            "0101",
            "Duplicate Dimmer",
            "DALI DT6 Dimmable Driver",
            "brightness",
        ),
    ]


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
def mock_gateway(mock_devices: list[MagicMock]) -> Generator[MagicMock]:
    """Return a mocked DaliGateway."""
    with (
        patch(
            "homeassistant.components.sunricher_dali_center.DaliGateway", autospec=True
        ) as mock_gateway_class,
        patch(
            "homeassistant.components.sunricher_dali_center.config_flow.DaliGateway",
            new=mock_gateway_class,
        ),
    ):
        mock_gateway = mock_gateway_class.return_value
        mock_gateway.gw_sn = "6A242121110E"
        mock_gateway.gw_ip = "192.168.1.100"
        mock_gateway.port = 1883
        mock_gateway.name = "Test Gateway"
        mock_gateway.username = "gateway_user"
        mock_gateway.passwd = "gateway_pass"
        mock_gateway.connect = AsyncMock()
        mock_gateway.disconnect = AsyncMock()
        mock_gateway.discover_devices = AsyncMock(return_value=mock_devices)
        yield mock_gateway


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.sunricher_dali_center.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry
