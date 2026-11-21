"""Common fixtures for the Fenecon Modbus tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from fenecon_modbus import FeneconData, FeneconDeviceInfo, GridMode, State
import pytest
from pytest_homeassistant.common import MockConfigEntry, load_json_object_fixture

from homeassistant.components.fenecon_modbus.const import CONF_UNIT_ID, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT

from . import HOST, SERIAL


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.fenecon_modbus.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def device_info() -> FeneconDeviceInfo:
    """Return the identification data of the FEMS."""
    return FeneconDeviceInfo(**load_json_object_fixture("device_info.json", DOMAIN))


@pytest.fixture
def data() -> FeneconData:
    """Return a snapshot of the FEMS data points."""
    values = load_json_object_fixture("data.json", DOMAIN)
    values["state"] = State(values["state"])
    values["grid_mode"] = GridMode(values["grid_mode"])
    return FeneconData(**values)


@pytest.fixture
def mock_fenecon_client(
    device_info: FeneconDeviceInfo, data: FeneconData
) -> Generator[MagicMock]:
    """Mock the Fenecon Modbus client for the integration and the config flow."""
    with (
        patch(
            "homeassistant.components.fenecon_modbus.FeneconModbusClient",
            autospec=True,
        ) as mock_client_cls,
        patch(
            "homeassistant.components.fenecon_modbus.config_flow.FeneconModbusClient",
            new=mock_client_cls,
        ),
    ):
        client = mock_client_cls.return_value
        client.host = HOST
        client.__aenter__.return_value = client
        client.read_device_info.return_value = device_info
        client.read_data.return_value = data
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="FENECON Home 10",
        unique_id=SERIAL,
        data={CONF_HOST: HOST, CONF_PORT: 502, CONF_UNIT_ID: 1},
    )
