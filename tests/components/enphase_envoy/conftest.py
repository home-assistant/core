"""Define test fixtures for Enphase Envoy."""
from unittest.mock import AsyncMock, Mock, patch

from pyenphase import (
    Envoy,
    EnvoyData,
    EnvoyInverter,
    EnvoySystemConsumption,
    EnvoySystemProduction,
    EnvoyTokenAuth,
)
import pytest

from homeassistant.components.enphase_envoy import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass: HomeAssistant, config, serial_number):
    """Define a config entry fixture."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="45a36e55aaddb2007c5f6602e0c38e72",
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


@pytest.fixture(name="mock_envoy")
def mock_envoy_fixture(serial_number, mock_authenticate, mock_setup, mock_auth):
    """Define a mocked Envoy fixture."""
    mock_envoy = Mock(spec=Envoy)
    mock_envoy.serial_number = serial_number
    mock_envoy.authenticate = mock_authenticate
    mock_envoy.setup = mock_setup
    mock_envoy.auth = mock_auth
    mock_envoy.data = EnvoyData(
        system_consumption=EnvoySystemConsumption(
            watt_hours_last_7_days=1234,
            watt_hours_lifetime=1234,
            watt_hours_today=1234,
            watts_now=1234,
        ),
        system_production=EnvoySystemProduction(
            watt_hours_last_7_days=1234,
            watt_hours_lifetime=1234,
            watt_hours_today=1234,
            watts_now=1234,
        ),
        inverters={
            "1": EnvoyInverter(
                serial_number="1",
                last_report_date=1,
                last_report_watts=1,
                max_report_watts=1,
            )
        },
        raw={"varies_by": "firmware_version"},
    )
    mock_envoy.update = AsyncMock(return_value=mock_envoy.data)
    return mock_envoy


@pytest.fixture(name="setup_enphase_envoy")
async def setup_enphase_envoy_fixture(hass, config, mock_envoy):
    """Define a fixture to set up Enphase Envoy."""
    with patch(
        "homeassistant.components.enphase_envoy.config_flow.Envoy",
        return_value=mock_envoy,
    ), patch(
        "homeassistant.components.enphase_envoy.Envoy",
        return_value=mock_envoy,
    ), patch(
        "homeassistant.components.enphase_envoy.PLATFORMS", []
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="mock_authenticate")
def mock_authenticate():
    """Define a mocked Envoy.authenticate fixture."""
    return AsyncMock()


@pytest.fixture(name="mock_auth")
def mock_auth(serial_number):
    """Define a mocked EnvoyAuth fixture."""
    return EnvoyTokenAuth("127.0.0.1", token="abc", envoy_serial=serial_number)


@pytest.fixture(name="mock_setup")
def mock_setup():
    """Define a mocked Envoy.setup fixture."""
    return AsyncMock()


@pytest.fixture(name="serial_number")
def serial_number_fixture():
    """Define a serial number fixture."""
    return "1234"
