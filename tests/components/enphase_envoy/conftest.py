"""Define test fixtures for Enphase Envoy."""
import json
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.components.enphase_envoy import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass: HomeAssistant, config, serial_number):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"Envoy {serial_number}" if serial_number else "Envoy",
        unique_id=serial_number,
        data=config,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture():
    """Define a config entry data fixture."""
    return {
        CONF_HOST: "1.1.1.1",
        CONF_NAME: "Envoy 1234",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }


@pytest.fixture(name="gateway_data", scope="package")
def gateway_data_fixture():
    """Define a fixture to return gateway data."""
    return json.loads(load_fixture("data.json", "enphase_envoy"))


@pytest.fixture(name="inverters_production_data", scope="package")
def inverters_production_data_fixture():
    """Define a fixture to return inverter production data."""
    return json.loads(load_fixture("inverters_production.json", "enphase_envoy"))


@pytest.fixture(name="mock_envoy_reader")
def mock_envoy_reader_fixture(
    gateway_data,
    mock_get_data,
    mock_get_full_serial_number,
    mock_inverters_production,
    serial_number,
):
    """Define a mocked EnvoyReader fixture."""
    mock_envoy_reader = Mock(
        getData=mock_get_data,
        get_full_serial_number=mock_get_full_serial_number,
        inverters_production=mock_inverters_production,
    )

    for key, value in gateway_data.items():
        setattr(mock_envoy_reader, key, AsyncMock(return_value=value))

    return mock_envoy_reader


@pytest.fixture(name="mock_get_full_serial_number")
def mock_get_full_serial_number_fixture(serial_number):
    """Define a mocked EnvoyReader.get_full_serial_number fixture."""
    return AsyncMock(return_value=serial_number)


@pytest.fixture(name="mock_get_data")
def mock_get_data_fixture():
    """Define a mocked EnvoyReader.getData fixture."""
    return AsyncMock()


@pytest.fixture(name="mock_inverters_production")
def mock_inverters_production_fixture(inverters_production_data):
    """Define a mocked EnvoyReader.inverters_production fixture."""
    return AsyncMock(return_value=inverters_production_data)


@pytest.fixture(name="setup_enphase_envoy")
async def setup_enphase_envoy_fixture(hass, config, mock_envoy_reader):
    """Define a fixture to set up Enphase Envoy."""
    with patch(
        "homeassistant.components.enphase_envoy.config_flow.EnvoyReader",
        return_value=mock_envoy_reader,
    ), patch(
        "homeassistant.components.enphase_envoy.EnvoyReader",
        return_value=mock_envoy_reader,
    ), patch(
        "homeassistant.components.enphase_envoy.PLATFORMS", []
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="serial_number")
def serial_number_fixture():
    """Define a serial number fixture."""
    return "1234"
