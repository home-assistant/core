"""Common fixtures for the Ecoforest tests."""
from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from pyecoforest.models.device import Alarm, Device, OperationMode, State
import pytest

from homeassistant.components.ecoforest import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock, None, None]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.ecoforest.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="config")
def config_fixture():
    """Define a config entry data fixture."""
    return {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }


@pytest.fixture(name="serial_number")
def serial_number_fixture():
    """Define a serial number fixture."""
    return "1234"


@pytest.fixture(name="mock_device")
def mock_device_fixture(serial_number):
    """Define a mocked Ecoforest device fixture."""
    mock = Mock(spec=Device)
    mock.model = "model-version"
    mock.model_name = "model-name"
    mock.firmware = "firmware-version"
    mock.serial_number = serial_number
    mock.operation_mode = OperationMode.POWER
    mock.on = False
    mock.state = State.OFF
    mock.power = 3
    mock.temperature = 21.5
    mock.alarm = Alarm.PELLETS
    mock.alarm_code = "A099"
    mock.environment_temperature = 23.5
    mock.cpu_temperature = 36.1
    mock.gas_temperature = 40.2
    mock.ntc_temperature = 24.2
    return mock


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass: HomeAssistant, config, serial_number):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="45a36e55aaddb2007c5f6602e0c38e72",
        title=f"Ecoforest {serial_number}",
        unique_id=serial_number,
        data=config,
    )
    entry.add_to_hass(hass)
    return entry
