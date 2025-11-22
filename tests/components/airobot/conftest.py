"""Common fixtures for the Airobot tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pyairobotrest.models import (
    SettingFlags,
    StatusFlags,
    ThermostatSettings,
    ThermostatStatus,
)
import pytest

from homeassistant.components.airobot.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.airobot.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_status() -> ThermostatStatus:
    """Create a mock thermostat status."""
    return ThermostatStatus(
        device_id="T01A1B2C3",
        hw_version=256,
        fw_version=300,
        temp_air=22.0,
        hum_air=45.0,
        temp_floor=None,
        co2=None,
        aqi=None,
        device_uptime=10000,
        heating_uptime=5000,
        errors=0,
        setpoint_temp=22.0,
        status_flags=StatusFlags(
            window_open_detected=False,
            heating_on=False,
        ),
    )


@pytest.fixture
def mock_settings() -> ThermostatSettings:
    """Create a mock thermostat settings."""
    return ThermostatSettings(
        device_id="T01A1B2C3",
        mode=1,
        setpoint_temp=22.0,
        setpoint_temp_away=18.0,
        hysteresis_band=0.1,
        device_name="Test Thermostat",
        setting_flags=SettingFlags(
            reboot=False,
            actuator_exercise_disabled=False,
            recalibrate_co2=False,
            childlock_enabled=False,
            boost_enabled=False,
        ),
    )


@pytest.fixture
def mock_airobot_client(
    mock_status: ThermostatStatus, mock_settings: ThermostatSettings
):
    """Mock AirobotClient for both coordinator and config flow."""
    with (
        patch(
            "homeassistant.components.airobot.coordinator.AirobotClient", autospec=True
        ) as mock_client,
        patch(
            "homeassistant.components.airobot.config_flow.AirobotClient",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_statuses.return_value = mock_status
        client.get_settings.return_value = mock_settings
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_USERNAME: "T01A1B2C3",
            CONF_PASSWORD: "test-password",
            CONF_MAC: "aa:bb:cc:dd:ee:ff",
        },
        unique_id="T01A1B2C3",
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airobot_client: AsyncMock,
) -> MockConfigEntry:
    """Set up the Airobot integration for testing."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry
