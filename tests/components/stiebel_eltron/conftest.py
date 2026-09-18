"""Common fixtures for the STIEBEL ELTRON tests."""

from collections.abc import AsyncGenerator, Generator
from unittest.mock import MagicMock, patch

from modbus_connection.mock import MockModbusConnection
from pystiebeleltron import ControllerModel
from pystiebeleltron.lwz import OperatingMode
import pytest

from homeassistant.components.stiebel_eltron.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_get_controller_model() -> Generator[MagicMock]:
    """Mock the Stiebel Eltron get_controller_model function."""
    with (
        patch(
            "homeassistant.components.stiebel_eltron.get_controller_model",
            autospec=True,
        ) as mock_get_model,
        patch(
            "homeassistant.components.stiebel_eltron.config_flow.get_controller_model",
            new=mock_get_model,
        ),
    ):
        mock_get_model.return_value = ControllerModel.LWZ
        yield mock_get_model


@pytest.fixture(autouse=True)
async def mock_modbus_connection_class(
    mock_modbus_connection: MockModbusConnection,
) -> AsyncGenerator[MagicMock]:
    """Let the modbus integration hand out units on the in-memory connection."""
    await mock_modbus_connection.connect()
    with patch(
        "homeassistant.components.modbus.connection.ModbusConnection",
        return_value=mock_modbus_connection,
    ) as mock_connection_cls:
        yield mock_connection_cls


@pytest.fixture(autouse=True)
def mock_lwz_api() -> Generator[MagicMock]:
    """Patch the LWZ API and return the mocked client."""

    with patch(
        "homeassistant.components.stiebel_eltron.coordinator.LwzStiebelEltronAPI",
        autospec=True,
    ) as mock_api_cls:
        api_client = mock_api_cls.return_value

        api_client.get_target_temp.return_value = 22.5
        api_client.get_current_temp.return_value = 21.0
        api_client.get_current_humidity.return_value = 45.0
        api_client.get_operation.return_value = OperatingMode.AUTOMATIC
        api_client.get_heating_status.return_value = True
        api_client.get_cooling_status.return_value = False
        api_client.get_filter_alarm_status.return_value = False

        yield api_client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Stiebel Eltron",
        data={CONF_HOST: "1.1.1.1", CONF_PORT: 502},
        entry_id="stiebel_eltron_001",
    )
