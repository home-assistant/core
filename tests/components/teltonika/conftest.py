"""Fixtures for Teltonika tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.teltonika.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry, load_json_object_fixture


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.teltonika.async_setup_entry",
        return_value=True,
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_teltasync() -> Generator[MagicMock]:
    """Mock Teltasync client."""
    with patch(
        "homeassistant.components.teltonika.config_flow.Teltasync",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value

        # Default device info
        device_info = MagicMock()
        device_info.device_name = "RUTX50 Test"
        device_info.device_identifier = "TEST1234567890"

        client.get_device_info = AsyncMock(return_value=device_info)
        client.validate_credentials = AsyncMock(return_value=True)
        client.close = AsyncMock()

        yield mock_client


@pytest.fixture
def mock_teltasync_client(mock_teltasync: MagicMock) -> MagicMock:
    """Return the client instance from mock_teltasync."""
    return mock_teltasync.return_value


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    # Load real device data for realistic config entry
    device_data = load_json_object_fixture("device_data.json", DOMAIN)
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Device",
        data={
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "test_password",
        },
        unique_id=device_data["system_info"]["mnf_info"]["serial"],
    )


@pytest.fixture
def mock_modems() -> Generator[MagicMock]:
    """Mock Modems class."""
    with patch(
        "homeassistant.components.teltonika.coordinator.Modems",
        autospec=True,
    ) as mock_modems_class:
        mock_modems_instance = mock_modems_class.return_value

        # Load device data to get modem info
        device_data = load_json_object_fixture("device_data.json", DOMAIN)
        modem_fixture = device_data["modems_data"][0]  # type: ignore[index]

        # Create modem object mock
        modem_mock = MagicMock()
        modem_mock.id = modem_fixture["id"]  # type: ignore[index]
        modem_mock.name = modem_fixture["name"]  # type: ignore[index]
        modem_mock.model = modem_fixture["model"]  # type: ignore[index]
        modem_mock.imei = modem_fixture["imei"]  # type: ignore[index]
        modem_mock.temperature = modem_fixture["temperature"]  # type: ignore[index]
        modem_mock.operator = modem_fixture["operator"]  # type: ignore[index]
        modem_mock.conntype = modem_fixture["conntype"]  # type: ignore[index]
        modem_mock.state = modem_fixture["state"]  # type: ignore[index]
        modem_mock.rssi = modem_fixture["rssi"]  # type: ignore[index]
        modem_mock.rsrp = modem_fixture["rsrp"]  # type: ignore[index]
        modem_mock.rsrq = modem_fixture["rsrq"]  # type: ignore[index]
        modem_mock.sinr = modem_fixture["sinr"]  # type: ignore[index]
        modem_mock.band = modem_fixture.get("band", "5G N3")  # type: ignore[union-attr]
        modem_mock.txbytes = modem_fixture.get("txbytes", 0)  # type: ignore[union-attr]
        modem_mock.rxbytes = modem_fixture.get("rxbytes", 0)  # type: ignore[union-attr]

        # Create response object with data attribute
        response_mock = MagicMock()
        response_mock.data = [modem_mock]

        mock_modems_instance.get_status = AsyncMock(return_value=response_mock)

        # Mock is_online to return True for the modem
        mock_modems_class.is_online = MagicMock(return_value=True)

        yield mock_modems_class


@pytest.fixture
def mock_teltasync_init() -> Generator[MagicMock]:
    """Mock Teltasync for init tests."""
    with patch(
        "homeassistant.components.teltonika.Teltasync",
        autospec=True,
    ) as mock_client:
        client = mock_client.return_value

        # Load device data
        device_data = load_json_object_fixture("device_data.json", DOMAIN)

        # Mock device info
        device_info = MagicMock()
        device_info.device_name = device_data["system_info"]["static"]["device_name"]
        device_info.device_identifier = device_data["system_info"]["mnf_info"]["serial"]

        # Mock system info - create a proper object structure
        system_info = MagicMock()
        system_info.mnf_info = MagicMock()
        system_info.mnf_info.serial = device_data["system_info"]["mnf_info"]["serial"]
        system_info.mnf_info.name = device_data["system_info"]["mnf_info"]["name"]
        system_info.static = MagicMock()
        system_info.static.device_name = device_data["system_info"]["static"][
            "device_name"
        ]
        system_info.static.model = device_data["system_info"]["static"]["model"]
        system_info.static.fw_version = device_data["system_info"]["static"][
            "fw_version"
        ]

        client.get_device_info = AsyncMock(return_value=device_info)
        client.get_system_info = AsyncMock(return_value=system_info)
        client.close = AsyncMock()

        yield mock_client
