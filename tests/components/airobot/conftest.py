"""Common fixtures for the Airobot tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from pyairobotmodbus.models import (
    AirobotData as VUData,
    AirobotIdentity,
    ErrorFlag,
    OperatingMode,
)
from pyairobotrest.models import (
    SettingFlags,
    StatusFlags,
    ThermostatSettings,
    ThermostatStatus,
)
import pytest

from homeassistant.components.airobot.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_USERNAME,
    Platform,
)
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
def platforms() -> list[Platform]:
    """Fixture to specify platforms to test."""
    return [Platform.CLIMATE, Platform.SENSOR]


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airobot_client: AsyncMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Airobot integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.airobot.THERMOSTAT_PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_config_entry


@pytest.fixture
def mock_vu_data() -> VUData:
    """Create mock VU data."""
    return VUData(
        firmware_version=100,
        extract_air_temp=22.5,
        supply_air_temp=21.0,
        outside_air_temp=5.0,
        exhaust_air_temp=8.0,
        extra_temp=18.5,
        extract_air_humidity=45.0,
        supply_air_humidity=35.0,
        outside_air_humidity=80.0,
        exhaust_air_humidity=90.0,
        extra_humidity=55.0,
        co2_level=450,
        voc=120,
        pm25=15,
        supply_fan_level=3,
        extract_fan_level=3,
        supply_fan_rpm=1200,
        extract_fan_rpm=1150,
        supply_airflow=120,
        extract_airflow=115,
        working_time_ms=3600000,
        error_flags=ErrorFlag.NONE,
        server_connected=True,
        heat_recovery_efficiency=85,
        operating_mode=OperatingMode.AUTOMATIC,
        humidity_setpoint=50.0,
        co2_setpoint=800,
        voc_setpoint=200,
        pm25_setpoint=25,
        manual_fan_level=5,
        overpressure_fan_level=7,
        boost_timeout=1200,
        overpressure_timeout=1800,
        filter_reminder_interval=4380,
        filter_reminder_elapsed=1000,
        power_on=True,
        bypass_on=False,
        boost_on=False,
        overpressure_on=False,
        filter_alert=False,
        humidity_control_enabled=True,
        voc_control_enabled=True,
        pm_control_enabled=False,
    )


@pytest.fixture
def mock_vu_client(mock_vu_data: VUData) -> Generator[AsyncMock]:
    """Mock AirobotModbusClient.

    autospec provides spec'd AsyncMocks for every method, so renamed or
    re-signatured library methods fail tests instead of drifting.
    """
    with (
        patch(
            "homeassistant.components.airobot.coordinator.AirobotModbusClient",
            autospec=True,
        ) as mock_client_class,
        patch(
            "homeassistant.components.airobot.config_flow.AirobotModbusClient",
            new=mock_client_class,
        ),
    ):
        client = mock_client_class.return_value
        client.async_get_data.return_value = mock_vu_data
        client.async_get_identity.return_value = AirobotIdentity(
            serial_number="01234567", mac_address="aa:bb:cc:dd:ee:ff"
        )
        yield client


@pytest.fixture
def mock_vu_config_entry() -> MockConfigEntry:
    """Mock a VU config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.200",
            "device_type": "ventilation",
            CONF_MAC: "aa:bb:cc:dd:ee:ff",
        },
        unique_id="aa:bb:cc:dd:ee:ff",
        title="Airobot Ventilation",
        entry_id="01JRVXRM5WBCVRAC076RFGNQF8",
    )


@pytest.fixture
async def init_vu_integration(
    hass: HomeAssistant,
    mock_vu_config_entry: MockConfigEntry,
    mock_vu_client: AsyncMock,
    platforms: list[Platform],
) -> MockConfigEntry:
    """Set up the Airobot VU integration for testing."""
    mock_vu_config_entry.add_to_hass(hass)

    with patch("homeassistant.components.airobot.VU_PLATFORMS", platforms):
        await hass.config_entries.async_setup(mock_vu_config_entry.entry_id)
        await hass.async_block_till_done()

    return mock_vu_config_entry
