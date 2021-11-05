"""Tests for the Fronius sensor platform."""
from datetime import timedelta

from homeassistant.components.fronius.const import (
    DEFAULT_UPDATE_INTERVAL,
    DEFAULT_UPDATE_INTERVAL_POWER_FLOW,
)
from homeassistant.const import STATE_UNKNOWN
from homeassistant.util import dt

from . import setup_fronius_integration
from .const import MOCK_HOST

from tests.common import async_fire_time_changed, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker


def mock_responses(aioclient_mock: AiohttpClientMocker, night: bool = False) -> None:
    """Mock responses for Fronius Symo inverter with meter."""
    aioclient_mock.clear_requests()
    _day_or_night = "night" if night else "day"

    aioclient_mock.get(
        f"{MOCK_HOST}/solar_api/GetAPIVersion.cgi",
        text=load_fixture("symo/GetAPIVersion.json", "fronius"),
    )
    aioclient_mock.get(
        f"{MOCK_HOST}/solar_api/v1/GetInverterRealtimeData.cgi?Scope=Device&"
        "DeviceId=1&DataCollection=CommonInverterData",
        text=load_fixture(
            f"symo/GetInverterRealtimeDate_Device_1_{_day_or_night}.json", "fronius"
        ),
    )
    aioclient_mock.get(
        f"{MOCK_HOST}/solar_api/v1/GetInverterInfo.cgi",
        text=load_fixture("symo/GetInverterInfo.json", "fronius"),
    )
    aioclient_mock.get(
        f"{MOCK_HOST}/solar_api/v1/GetLoggerInfo.cgi",
        text=load_fixture("symo/GetLoggerInfo.json", "fronius"),
    )
    aioclient_mock.get(
        f"{MOCK_HOST}/solar_api/v1/GetMeterRealtimeData.cgi?Scope=Device&DeviceId=0",
        text=load_fixture("symo/GetMeterRealtimeData_Device_0.json", "fronius"),
    )
    aioclient_mock.get(
        f"{MOCK_HOST}/solar_api/v1/GetMeterRealtimeData.cgi?Scope=System",
        text=load_fixture("symo/GetMeterRealtimeData_System.json", "fronius"),
    )
    aioclient_mock.get(
        f"{MOCK_HOST}/solar_api/v1/GetPowerFlowRealtimeData.fcgi",
        text=load_fixture(
            f"symo/GetPowerFlowRealtimeData_{_day_or_night}.json", "fronius"
        ),
    )
    aioclient_mock.get(
        f"{MOCK_HOST}/solar_api/v1/GetStorageRealtimeData.cgi?Scope=System",
        text=load_fixture("symo/GetStorageRealtimeData_System.json", "fronius"),
    )


async def test_symo_inverter(hass, aioclient_mock):
    """Test Fronius Symo inverter entities."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state.state == str(expected_state)

    # Init at night
    mock_responses(aioclient_mock, night=True)
    await setup_fronius_integration(hass)

    assert len(hass.states.async_all()) == 55
    assert_state("sensor.fronius_inverter_1_current_dc", 0)
    assert_state("sensor.fronius_inverter_1_energy_day", 10828)
    assert_state("sensor.fronius_inverter_1_energy_total", 44186900)
    assert_state("sensor.fronius_inverter_1_energy_year", 25507686)
    assert_state("sensor.fronius_inverter_1_voltage_dc", 16)

    # Second test at daytime when inverter is producing
    mock_responses(aioclient_mock, night=False)
    async_fire_time_changed(
        hass, dt.utcnow() + timedelta(seconds=DEFAULT_UPDATE_INTERVAL)
    )
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 59
    # 4 additional AC entities
    assert_state("sensor.fronius_inverter_1_current_dc", 2.19)
    assert_state("sensor.fronius_inverter_1_energy_day", 1113)
    assert_state("sensor.fronius_inverter_1_energy_total", 44188000)
    assert_state("sensor.fronius_inverter_1_energy_year", 25508798)
    assert_state("sensor.fronius_inverter_1_voltage_dc", 518)
    assert_state("sensor.fronius_inverter_1_current_ac", 5.19)
    assert_state("sensor.fronius_inverter_1_frequency_ac", 49.94)
    assert_state("sensor.fronius_inverter_1_power_ac", 1190)
    assert_state("sensor.fronius_inverter_1_voltage_ac", 227.90)


async def test_symo_logger(hass, aioclient_mock):
    """Test Fronius Symo logger entities."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == str(expected_state)

    mock_responses(aioclient_mock)
    await setup_fronius_integration(hass)

    assert len(hass.states.async_all()) == 59
    # ignored constant entities:
    # hardware_platform, hardware_version, product_type
    # software_version, time_zone, time_zone_location
    # time_stamp, unique_identifier, utc_offset
    #
    # states are rounded to 2 decimals
    assert_state(
        "sensor.fronius_logger_cash_factor",
        0.078,
    )
    assert_state(
        "sensor.fronius_logger_co2_factor",
        0.53,
    )
    assert_state(
        "sensor.fronius_logger_delivery_factor",
        0.15,
    )


async def test_symo_meter(hass, aioclient_mock):
    """Test Fronius Symo meter entities."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == str(expected_state)

    mock_responses(aioclient_mock)
    await setup_fronius_integration(hass)

    assert len(hass.states.async_all()) == 59
    # ignored entities:
    # manufacturer, model, serial, enable, timestamp, visible, meter_location
    #
    # states are rounded to 2 decimals
    assert_state("sensor.fronius_meter_0_current_ac_phase_1", 7.755)
    assert_state("sensor.fronius_meter_0_current_ac_phase_2", 6.68)
    assert_state("sensor.fronius_meter_0_current_ac_phase_3", 10.102)
    assert_state("sensor.fronius_meter_0_energy_reactive_ac_consumed", 59960790)
    assert_state("sensor.fronius_meter_0_energy_reactive_ac_produced", 723160)
    assert_state("sensor.fronius_meter_0_energy_real_ac_minus", 35623065)
    assert_state("sensor.fronius_meter_0_energy_real_ac_plus", 15303334)
    assert_state("sensor.fronius_meter_0_energy_real_consumed", 15303334)
    assert_state("sensor.fronius_meter_0_energy_real_produced", 35623065)
    assert_state("sensor.fronius_meter_0_frequency_phase_average", 50)
    assert_state("sensor.fronius_meter_0_power_apparent_phase_1", 1772.793)
    assert_state("sensor.fronius_meter_0_power_apparent_phase_2", 1527.048)
    assert_state("sensor.fronius_meter_0_power_apparent_phase_3", 2333.562)
    assert_state("sensor.fronius_meter_0_power_apparent", 5592.57)
    assert_state("sensor.fronius_meter_0_power_factor_phase_1", -0.99)
    assert_state("sensor.fronius_meter_0_power_factor_phase_2", -0.99)
    assert_state("sensor.fronius_meter_0_power_factor_phase_3", 0.99)
    assert_state("sensor.fronius_meter_0_power_factor", 1)
    assert_state("sensor.fronius_meter_0_power_reactive_phase_1", 51.48)
    assert_state("sensor.fronius_meter_0_power_reactive_phase_2", 115.63)
    assert_state("sensor.fronius_meter_0_power_reactive_phase_3", -164.24)
    assert_state("sensor.fronius_meter_0_power_reactive", 2.87)
    assert_state("sensor.fronius_meter_0_power_real_phase_1", 1765.55)
    assert_state("sensor.fronius_meter_0_power_real_phase_2", 1515.8)
    assert_state("sensor.fronius_meter_0_power_real_phase_3", 2311.22)
    assert_state("sensor.fronius_meter_0_power_real", 5592.57)
    assert_state("sensor.fronius_meter_0_voltage_ac_phase_1", 228.6)
    assert_state("sensor.fronius_meter_0_voltage_ac_phase_2", 228.6)
    assert_state("sensor.fronius_meter_0_voltage_ac_phase_3", 231)
    assert_state("sensor.fronius_meter_0_voltage_ac_phase_to_phase_12", 395.9)
    assert_state("sensor.fronius_meter_0_voltage_ac_phase_to_phase_23", 398)
    assert_state("sensor.fronius_meter_0_voltage_ac_phase_to_phase_31", 398)


async def test_symo_power_flow(hass, aioclient_mock):
    """Test Fronius Symo power flow entities."""
    async_fire_time_changed(hass, dt.utcnow())

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state.state == str(expected_state)

    # First test at night
    mock_responses(aioclient_mock, night=True)
    await setup_fronius_integration(hass)

    assert len(hass.states.async_all()) == 55
    # ignored: location, mode, timestamp
    #
    # states are rounded to 2 decimals
    assert_state("sensor.fronius_powerflow_energy_day", 10828)
    assert_state("sensor.fronius_powerflow_energy_total", 44186900)
    assert_state("sensor.fronius_powerflow_energy_year", 25507686)
    assert_state("sensor.fronius_powerflow_power_battery", STATE_UNKNOWN)
    assert_state("sensor.fronius_powerflow_power_grid", 975.31)
    assert_state("sensor.fronius_powerflow_power_load", -975.31)
    assert_state("sensor.fronius_powerflow_power_photovoltaics", STATE_UNKNOWN)
    assert_state("sensor.fronius_powerflow_relative_autonomy", 0)
    assert_state("sensor.fronius_powerflow_relative_self_consumption", STATE_UNKNOWN)

    # Second test at daytime when inverter is producing
    mock_responses(aioclient_mock, night=False)
    async_fire_time_changed(
        hass, dt.utcnow() + timedelta(seconds=DEFAULT_UPDATE_INTERVAL_POWER_FLOW)
    )
    await hass.async_block_till_done()
    # still 55 because power_flow update interval is shorter than others
    assert len(hass.states.async_all()) == 55
    assert_state("sensor.fronius_powerflow_energy_day", 1101.7001)
    assert_state("sensor.fronius_powerflow_energy_total", 44188000)
    assert_state("sensor.fronius_powerflow_energy_year", 25508788)
    assert_state("sensor.fronius_powerflow_power_battery", STATE_UNKNOWN)
    assert_state("sensor.fronius_powerflow_power_grid", 1703.74)
    assert_state("sensor.fronius_powerflow_power_load", -2814.74)
    assert_state("sensor.fronius_powerflow_power_photovoltaics", 1111)
    assert_state("sensor.fronius_powerflow_relative_autonomy", 39.4708)
    assert_state("sensor.fronius_powerflow_relative_self_consumption", 100)
