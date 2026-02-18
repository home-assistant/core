"""Fixtures for Teltonika tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from teltasync.modems import ModemStatusFull
from teltasync.system import DeviceStatusData
from teltasync.unauthorized import UnauthorizedStatusData

from homeassistant.components.teltonika.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

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
    """Mock Teltasync client for both config flow and init."""
    with (
        patch(
            "homeassistant.components.teltonika.config_flow.Teltasync",
            autospec=True,
        ) as mock_teltasync_class,
        patch(
            "homeassistant.components.teltonika.Teltasync",
            new=mock_teltasync_class,
        ),
    ):
        shared_client = mock_teltasync_class.return_value

        device_info = load_json_object_fixture("device_info.json", DOMAIN)
        shared_client.get_device_info.return_value = UnauthorizedStatusData(
            **device_info
        )

        system_info = load_json_object_fixture("system_info.json", DOMAIN)
        shared_client.get_system_info.return_value = DeviceStatusData(**system_info)

        yield mock_teltasync_class


@pytest.fixture
def mock_teltasync_client(mock_teltasync: MagicMock) -> MagicMock:
    """Return the client instance from mock_teltasync."""
    return mock_teltasync.return_value


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    device_data = load_json_object_fixture("device_data.json", DOMAIN)
    return MockConfigEntry(
        domain=DOMAIN,
        title="RUTX50 Test",
        data={
            CONF_HOST: "192.168.1.1",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "test_password",
        },
        unique_id=device_data["system_info"]["mnf_info"]["serial"],
    )


@pytest.fixture
def mock_modems() -> Generator[AsyncMock]:
    """Mock Modems class."""
    with patch(
        "homeassistant.components.teltonika.coordinator.Modems",
        autospec=True,
    ) as mock_modems_class:
        mock_modems_instance = mock_modems_class.return_value

        # Load device data to get modem info
        device_data = load_json_object_fixture("device_data.json", DOMAIN)
        # Create response object with data attribute
        response_mock = MagicMock()
        response_mock.data = [
            ModemStatusFull(**modem) for modem in device_data["modems_data"]
        ]
        mock_modems_instance.get_status.return_value = response_mock

        # Mock is_online to return True for the modem
        mock_modems_class.is_online = MagicMock(return_value=True)

        yield mock_modems_instance


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_teltasync: MagicMock,
    mock_modems: MagicMock,
) -> MockConfigEntry:
    """Set up the Teltonika integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
