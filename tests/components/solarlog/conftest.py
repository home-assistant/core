"""Test helpers."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from solarlog_cli.solarlog_models import InverterData, SolarlogData

from homeassistant.components.solarlog.const import (
    CONF_HAS_PWD,
    DOMAIN as SOLARLOG_DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD

from .const import HOST, NAME

from tests.common import MockConfigEntry, load_json_object_fixture

DEVICE_LIST = {
    0: InverterData(name="Inverter 1", enabled=True),
    1: InverterData(name="Inverter 2", enabled=True),
}
INVERTER_DATA = {
    0: InverterData(
        name="Inverter 1", enabled=True, consumption_year=354687, current_power=5
    ),
    1: InverterData(
        name="Inverter 2", enabled=True, consumption_year=354, current_power=6
    ),
}


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=SOLARLOG_DOMAIN,
        title="solarlog",
        data={
            CONF_HOST: HOST,
            CONF_NAME: NAME,
            CONF_HAS_PWD: True,
            CONF_PASSWORD: "pwd",
        },
        minor_version=3,
        entry_id="ce5f5431554d101905d31797e1232da8",
    )


@pytest.fixture
def mock_solarlog_connector():
    """Build a fixture for the SolarLog API that connects successfully and returns one device."""

    data = SolarlogData.from_dict(
        load_json_object_fixture("solarlog_data.json", SOLARLOG_DOMAIN)
    )
    data.inverter_data = INVERTER_DATA

    mock_solarlog_api = AsyncMock()
    mock_solarlog_api.set_enabled_devices = MagicMock()
    mock_solarlog_api.test_connection.return_value = True
    mock_solarlog_api.test_extended_data_available.return_value = True
    mock_solarlog_api.extended_data.return_value = True
    mock_solarlog_api.update_data.return_value = data
    mock_solarlog_api.update_device_list.return_value = DEVICE_LIST
    mock_solarlog_api.update_inverter_data.return_value = INVERTER_DATA
    mock_solarlog_api.device_name = {0: "Inverter 1", 1: "Inverter 2"}.get
    mock_solarlog_api.device_enabled = {0: True, 1: True}.get
    mock_solarlog_api.password.return_value = "pwd"

    with (
        patch(
            "homeassistant.components.solarlog.coordinator.SolarLogConnector",
            autospec=True,
            return_value=mock_solarlog_api,
        ),
        patch(
            "homeassistant.components.solarlog.config_flow.SolarLogConnector",
            autospec=True,
            return_value=mock_solarlog_api,
        ),
    ):
        yield mock_solarlog_api


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.solarlog.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(name="test_connect")
def mock_test_connection():
    """Mock a successful _test_connection."""
    with patch(
        "homeassistant.components.solarlog.config_flow.SolarLogConfigFlow._test_connection",
        return_value=True,
    ):
        yield
