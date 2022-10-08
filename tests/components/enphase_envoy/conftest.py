"""Define test fixtures for Enphase Envoy."""
from unittest.mock import AsyncMock, patch

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
        title=f"Envoy {serial_number}" if serial_number else "Envoy",
        unique_id=serial_number,
        data=config,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture(name="config")
def config_fixture(hass: HomeAssistant):
    """Define a config entry data fixture."""
    return {
        CONF_HOST: "1.1.1.1",
        CONF_NAME: "Envoy 1234",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }


@pytest.fixture(name="mock_get_data")
async def mock_get_data_fixture(hass: HomeAssistant, config, serial_number):
    """Define a fixture to return a mocked data coroutine function."""
    return AsyncMock(return_value=True)


@pytest.fixture(name="mock_get_full_serial_number")
async def mock_get_full_serial_number_fixture(
    hass: HomeAssistant, config, serial_number
):
    """Define a fixture to return a mocked serial number coroutine function."""
    return AsyncMock(return_value=serial_number)


@pytest.fixture(name="setup_enphase_envoy")
async def setup_enphase_envoy_fixture(
    hass, config, mock_get_data, mock_get_full_serial_number
):
    """Define a fixture to set up Enphase Envoy."""
    with patch(
        "homeassistant.components.enphase_envoy.config_flow.EnvoyReader.getData",
        mock_get_data,
    ), patch(
        "homeassistant.components.enphase_envoy.config_flow.EnvoyReader.get_full_serial_number",
        mock_get_full_serial_number,
    ), patch(
        "homeassistant.components.enphase_envoy.PLATFORMS", []
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


@pytest.fixture(name="serial_number")
def serial_number_fixture(hass: HomeAssistant):
    """Define a serial number fixture."""
    return "1234"
