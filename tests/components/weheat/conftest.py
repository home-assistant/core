"""Fixtures for Weheat tests."""

from collections.abc import Generator
from time import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from weheat.abstractions.discovery import HeatPumpDiscovery
from weheat.abstractions.heat_pump import HeatPump

from homeassistant.components.application_credentials import (
    DOMAIN as APPLICATION_CREDENTIALS,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.weheat.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import (
    CLIENT_ID,
    CLIENT_SECRET,
    TEST_HP_UUID,
    TEST_MODEL,
    TEST_SN,
    USER_UUID_1,
)

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, APPLICATION_CREDENTIALS, {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


@pytest.fixture
def mock_setup_entry():
    """Mock a successful setup."""
    with patch(
        "homeassistant.components.weheat.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture
def mock_heat_pump_info() -> HeatPumpDiscovery.HeatPumpInfo:
    """Create a HeatPumpInfo with default settings."""
    return HeatPumpDiscovery.HeatPumpInfo(TEST_HP_UUID, None, TEST_MODEL, TEST_SN, True)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Weheat",
        data={
            "id": "12345",
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "expires_at": time() + 60,
            },
        },
        unique_id="123456789",
    )


@pytest.fixture
def mock_user_id() -> Generator[AsyncMock]:
    """Mock the user API call."""
    with (
        patch(
            "homeassistant.components.weheat.config_flow.get_user_id_from_token",
            return_value=USER_UUID_1,
        ) as user_mock,
    ):
        yield user_mock


@pytest.fixture
def mock_weheat_discover(mock_heat_pump_info) -> Generator[AsyncMock]:
    """Mock an Weheat discovery."""
    with (
        patch(
            "homeassistant.components.weheat.HeatPumpDiscovery.discover_active",
            autospec=True,
        ) as mock_discover,
    ):
        mock_discover.return_value = [mock_heat_pump_info]

        yield mock_discover


@pytest.fixture
def mock_weheat_heat_pump_instance() -> MagicMock:
    """Mock an Weheat heat pump instance with a set of default values."""
    mock_heat_pump_instance = MagicMock(spec_set=HeatPump)

    mock_heat_pump_instance.water_inlet_temperature = 11
    mock_heat_pump_instance.water_outlet_temperature = 22
    mock_heat_pump_instance.water_house_in_temperature = 33
    mock_heat_pump_instance.air_inlet_temperature = 44
    mock_heat_pump_instance.power_input = 55
    mock_heat_pump_instance.power_output = 66
    mock_heat_pump_instance.dhw_top_temperature = 77
    mock_heat_pump_instance.dhw_bottom_temperature = 88
    mock_heat_pump_instance.thermostat_water_setpoint = 35
    mock_heat_pump_instance.thermostat_room_temperature = 19
    mock_heat_pump_instance.thermostat_room_temperature_setpoint = 21
    mock_heat_pump_instance.cop = 4.5
    mock_heat_pump_instance.heat_pump_state = HeatPump.State.HEATING
    mock_heat_pump_instance.energy_total = 12345
    mock_heat_pump_instance.energy_output = 56789
    mock_heat_pump_instance.compressor_rpm = 4500
    mock_heat_pump_instance.compressor_percentage = 100
    mock_heat_pump_instance.indoor_unit_water_pump_state = False
    mock_heat_pump_instance.indoor_unit_auxiliary_pump_state = False
    mock_heat_pump_instance.indoor_unit_dhw_valve_or_pump_state = None
    mock_heat_pump_instance.indoor_unit_gas_boiler_state = False
    mock_heat_pump_instance.indoor_unit_electric_heater_state = True

    return mock_heat_pump_instance


@pytest.fixture
def mock_weheat_heat_pump(mock_weheat_heat_pump_instance) -> Generator[AsyncMock]:
    """Mock the coordinator HeatPump data."""
    with (
        patch(
            "homeassistant.components.weheat.coordinator.HeatPump",
        ) as mock_heat_pump,
    ):
        mock_heat_pump.return_value = mock_weheat_heat_pump_instance

        yield mock_weheat_heat_pump_instance
