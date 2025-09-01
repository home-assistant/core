"""Common fixtures for the Dali Center tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.dali_center.const import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            "sn": "6A242121110E",
            "gateway": {"gw_sn": "6A242121110E", "gw_ip": "192.168.1.100"},
            "devices": [
                {
                    "unique_id": "01010000026A242121110E",
                    "id": "01010000026A242121110E",
                    "name": "Dimmer 0000-02",
                    "dev_type": "0101",
                    "channel": 0,
                    "address": 2,
                    "status": "online",
                    "dev_sn": "71DF763153191241",
                    "area_name": "",
                    "area_id": "",
                    "prop": [],
                },
                {
                    "unique_id": "01020000036A242121110E",
                    "id": "01020000036A242121110E",
                    "name": "CCT 0000-03",
                    "dev_type": "0102",
                    "channel": 0,
                    "address": 3,
                    "status": "online",
                    "dev_sn": "58405A2908C0DEB9",
                    "area_name": "",
                    "area_id": "",
                    "prop": [],
                },
            ],
        },
        unique_id="6A242121110E",
        title="Test Gateway",
    )


@pytest.fixture
def mock_devices() -> Generator[list[MagicMock]]:
    """Return mocked Device objects."""
    with patch(
        "homeassistant.components.dali_center.light.Device"
    ) as mock_device_class:
        device1 = MagicMock()
        device1.dev_id = "01010000026A242121110E"
        device1.unique_id = "01010000026A242121110E"
        device1.status = "online"
        device1.dev_type = "0101"
        device1.name = "Dimmer 0000-02"
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
        device2.gw_sn = "6A242121110E"
        device2.color_mode = "color_temp"
        device2.turn_on = MagicMock()
        device2.turn_off = MagicMock()
        device2.read_status = MagicMock()

        devices = [device1, device2]
        mock_device_class.side_effect = devices

        yield devices


@pytest.fixture
def mock_discovery() -> Generator[MagicMock]:
    """Mock DaliGatewayDiscovery."""
    with patch(
        "homeassistant.components.dali_center.config_flow.DaliGatewayDiscovery"
    ) as mock_discovery_class:
        mock_discovery = mock_discovery_class.return_value
        mock_discovery.discover_gateways = AsyncMock()
        yield mock_discovery


@pytest.fixture
def mock_validate_input() -> Generator[MagicMock]:
    """Mock validate_input function."""
    with patch(
        "homeassistant.components.dali_center.config_flow.validate_input"
    ) as mock_validate:
        yield mock_validate


@pytest.fixture
def mock_dali_gateway_class() -> Generator[MagicMock]:
    """Mock DaliGateway class for config flow."""
    with patch(
        "homeassistant.components.dali_center.config_flow.DaliGateway"
    ) as mock_class:
        mock_gateway = MagicMock()
        mock_gateway.connect = AsyncMock()
        mock_gateway.disconnect = AsyncMock()
        mock_gateway.discover_devices = AsyncMock(return_value=[])
        mock_gateway.to_dict = MagicMock(
            return_value={"gw_sn": "TEST123", "gw_ip": "192.168.1.100"}
        )
        mock_gateway.name = "Test Gateway"
        mock_class.return_value = mock_gateway
        yield mock_class


@pytest.fixture
def mock_dali_gateway() -> Generator[MagicMock]:
    """Return a mocked DaliGateway."""
    with patch(
        "homeassistant.components.dali_center.DaliGateway", autospec=True
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
        "homeassistant.components.dali_center.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry
