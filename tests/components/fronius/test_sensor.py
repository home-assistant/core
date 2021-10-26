"""Tests for the Fronius sensor platform."""

from homeassistant.components.fronius.sensor import (
    CONF_SCOPE,
    DEFAULT_SCAN_INTERVAL,
    SCOPE_DEVICE,
    TYPE_INVERTER,
    TYPE_LOGGER_INFO,
    TYPE_METER,
    TYPE_POWER_FLOW,
)
from homeassistant.const import CONF_DEVICE, CONF_SENSOR_TYPE, STATE_UNKNOWN
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
        text=load_fixture("fronius/symo/GetAPIVersion.json"),
    )
    aioclient_mock.get(
        f"{MOCK_HOST}/solar_api/v1/GetInverterRealtimeData.cgi?Scope=Device&"
        "DeviceId=1&DataCollection=CommonInverterData",
        text=load_fixture(
            f"fronius/symo/GetInverterRealtimeDate_Device_1_{_day_or_night}.json"
        ),
    )
    aioclient_mock.get(
        f"{MOCK_HOST}/solar_api/v1/GetInverterInfo.cgi",
        text=load_fixture("fronius/symo/GetInverterInfo.json"),
    )
    aioclient_mock.get(
        f"{MOCK_HOST}/solar_api/v1/GetLoggerInfo.cgi",
        text=load_fixture("fronius/symo/GetLoggerInfo.json"),
    )
    aioclient_mock.get(
        f"{MOCK_HOST}/solar_api/v1/GetMeterRealtimeData.cgi?Scope=Device&DeviceId=0",
        text=load_fixture("fronius/symo/GetMeterRealtimeData_Device_0.json"),
    )
    aioclient_mock.get(
        f"{MOCK_HOST}/solar_api/v1/GetMeterRealtimeData.cgi?Scope=System",
        text=load_fixture("fronius/symo/GetMeterRealtimeData_System.json"),
    )
    aioclient_mock.get(
        f"{MOCK_HOST}/solar_api/v1/GetPowerFlowRealtimeData.fcgi",
        text=load_fixture(
            f"fronius/symo/GetPowerFlowRealtimeData_{_day_or_night}.json"
        ),
    )
    aioclient_mock.get(
        f"{MOCK_HOST}/solar_api/v1/GetStorageRealtimeData.cgi?Scope=System",
        text=load_fixture("fronius/symo/GetStorageRealtimeData_System.json"),
    )


async def test_symo_inverter(hass, aioclient_mock):
    """Test Fronius Symo inverter entities."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state.state == str(expected_state)

    # Init at night
    mock_responses(aioclient_mock, night=True)
    config = {
        CONF_SENSOR_TYPE: TYPE_INVERTER,
        CONF_SCOPE: SCOPE_DEVICE,
        CONF_DEVICE: 1,
    }
    await setup_fronius_integration(hass, [config])

    assert len(hass.states.async_all()) == 10
    # 5 ignored from DeviceStatus
    assert_state("sensor.current_dc_fronius_inverter_1_http_fronius", 0)
    assert_state("sensor.energy_day_fronius_inverter_1_http_fronius", 10828)
    assert_state("sensor.energy_total_fronius_inverter_1_http_fronius", 44186900)
    assert_state("sensor.energy_year_fronius_inverter_1_http_fronius", 25507686)
    assert_state("sensor.voltage_dc_fronius_inverter_1_http_fronius", 16)

    # Second test at daytime when inverter is producing
    mock_responses(aioclient_mock, night=False)
    async_fire_time_changed(hass, dt.utcnow() + DEFAULT_SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 14
    # 4 additional AC entities
    assert_state("sensor.current_dc_fronius_inverter_1_http_fronius", 2.19)
    assert_state("sensor.energy_day_fronius_inverter_1_http_fronius", 1113)
    assert_state("sensor.energy_total_fronius_inverter_1_http_fronius", 44188000)
    assert_state("sensor.energy_year_fronius_inverter_1_http_fronius", 25508798)
    assert_state("sensor.voltage_dc_fronius_inverter_1_http_fronius", 518)
    assert_state("sensor.current_ac_fronius_inverter_1_http_fronius", 5.19)
    assert_state("sensor.frequency_ac_fronius_inverter_1_http_fronius", 49.94)
    assert_state("sensor.power_ac_fronius_inverter_1_http_fronius", 1190)
    assert_state("sensor.voltage_ac_fronius_inverter_1_http_fronius", 227.90)


async def test_symo_logger(hass, aioclient_mock):
    """Test Fronius Symo logger entities."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == str(expected_state)

    mock_responses(aioclient_mock)
    config = {
        CONF_SENSOR_TYPE: TYPE_LOGGER_INFO,
    }
    await setup_fronius_integration(hass, [config])

    assert len(hass.states.async_all()) == 12
    # ignored constant entities:
    # hardware_platform, hardware_version, product_type
    # software_version, time_zone, time_zone_location
    # time_stamp, unique_identifier, utc_offset
    #
    # states are rounded to 2 decimals
    assert_state(
        "sensor.cash_factor_fronius_logger_info_0_http_fronius",
        0.08,
    )
    assert_state(
        "sensor.co2_factor_fronius_logger_info_0_http_fronius",
        0.53,
    )
    assert_state(
        "sensor.delivery_factor_fronius_logger_info_0_http_fronius",
        0.15,
    )


async def test_symo_meter(hass, aioclient_mock):
    """Test Fronius Symo meter entities."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == str(expected_state)

    mock_responses(aioclient_mock)
    config = {
        CONF_SENSOR_TYPE: TYPE_METER,
        CONF_SCOPE: SCOPE_DEVICE,
        CONF_DEVICE: 0,
    }
    await setup_fronius_integration(hass, [config])

    assert len(hass.states.async_all()) == 39
    # ignored entities:
    # manufacturer, model, serial, enable, timestamp, visible, meter_location
    #
    # states are rounded to 2 decimals
    assert_state("sensor.current_ac_phase_1_fronius_meter_0_http_fronius", 7.75)
    assert_state("sensor.current_ac_phase_2_fronius_meter_0_http_fronius", 6.68)
    assert_state("sensor.current_ac_phase_3_fronius_meter_0_http_fronius", 10.1)
    assert_state(
        "sensor.energy_reactive_ac_consumed_fronius_meter_0_http_fronius", 59960790
    )
    assert_state(
        "sensor.energy_reactive_ac_produced_fronius_meter_0_http_fronius", 723160
    )
    assert_state("sensor.energy_real_ac_minus_fronius_meter_0_http_fronius", 35623065)
    assert_state("sensor.energy_real_ac_plus_fronius_meter_0_http_fronius", 15303334)
    assert_state("sensor.energy_real_consumed_fronius_meter_0_http_fronius", 15303334)
    assert_state("sensor.energy_real_produced_fronius_meter_0_http_fronius", 35623065)
    assert_state("sensor.frequency_phase_average_fronius_meter_0_http_fronius", 50)
    assert_state("sensor.power_apparent_phase_1_fronius_meter_0_http_fronius", 1772.79)
    assert_state("sensor.power_apparent_phase_2_fronius_meter_0_http_fronius", 1527.05)
    assert_state("sensor.power_apparent_phase_3_fronius_meter_0_http_fronius", 2333.56)
    assert_state("sensor.power_apparent_fronius_meter_0_http_fronius", 5592.57)
    assert_state("sensor.power_factor_phase_1_fronius_meter_0_http_fronius", -0.99)
    assert_state("sensor.power_factor_phase_2_fronius_meter_0_http_fronius", -0.99)
    assert_state("sensor.power_factor_phase_3_fronius_meter_0_http_fronius", 0.99)
    assert_state("sensor.power_factor_fronius_meter_0_http_fronius", 1)
    assert_state("sensor.power_reactive_phase_1_fronius_meter_0_http_fronius", 51.48)
    assert_state("sensor.power_reactive_phase_2_fronius_meter_0_http_fronius", 115.63)
    assert_state("sensor.power_reactive_phase_3_fronius_meter_0_http_fronius", -164.24)
    assert_state("sensor.power_reactive_fronius_meter_0_http_fronius", 2.87)
    assert_state("sensor.power_real_phase_1_fronius_meter_0_http_fronius", 1765.55)
    assert_state("sensor.power_real_phase_2_fronius_meter_0_http_fronius", 1515.8)
    assert_state("sensor.power_real_phase_3_fronius_meter_0_http_fronius", 2311.22)
    assert_state("sensor.power_real_fronius_meter_0_http_fronius", 5592.57)
    assert_state("sensor.voltage_ac_phase_1_fronius_meter_0_http_fronius", 228.6)
    assert_state("sensor.voltage_ac_phase_2_fronius_meter_0_http_fronius", 228.6)
    assert_state("sensor.voltage_ac_phase_3_fronius_meter_0_http_fronius", 231)
    assert_state(
        "sensor.voltage_ac_phase_to_phase_12_fronius_meter_0_http_fronius", 395.9
    )
    assert_state(
        "sensor.voltage_ac_phase_to_phase_23_fronius_meter_0_http_fronius", 398
    )
    assert_state(
        "sensor.voltage_ac_phase_to_phase_31_fronius_meter_0_http_fronius", 398
    )


async def test_symo_power_flow(hass, aioclient_mock):
    """Test Fronius Symo power flow entities."""
    async_fire_time_changed(hass, dt.utcnow())

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state.state == str(expected_state)

    # First test at night
    mock_responses(aioclient_mock, night=True)
    config = {
        CONF_SENSOR_TYPE: TYPE_POWER_FLOW,
    }
    await setup_fronius_integration(hass, [config])

    assert len(hass.states.async_all()) == 12
    # ignored: location, mode, timestamp
    #
    # states are rounded to 2 decimals
    assert_state(
        "sensor.energy_day_fronius_power_flow_0_http_fronius",
        10828,
    )
    assert_state(
        "sensor.energy_total_fronius_power_flow_0_http_fronius",
        44186900,
    )
    assert_state(
        "sensor.energy_year_fronius_power_flow_0_http_fronius",
        25507686,
    )
    assert_state(
        "sensor.power_battery_fronius_power_flow_0_http_fronius",
        STATE_UNKNOWN,
    )
    assert_state(
        "sensor.power_grid_fronius_power_flow_0_http_fronius",
        975.31,
    )
    assert_state(
        "sensor.power_load_fronius_power_flow_0_http_fronius",
        -975.31,
    )
    assert_state(
        "sensor.power_photovoltaics_fronius_power_flow_0_http_fronius",
        STATE_UNKNOWN,
    )
    assert_state(
        "sensor.relative_autonomy_fronius_power_flow_0_http_fronius",
        0,
    )
    assert_state(
        "sensor.relative_self_consumption_fronius_power_flow_0_http_fronius",
        STATE_UNKNOWN,
    )

    # Second test at daytime when inverter is producing
    mock_responses(aioclient_mock, night=False)
    async_fire_time_changed(hass, dt.utcnow() + DEFAULT_SCAN_INTERVAL)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 12
    assert_state(
        "sensor.energy_day_fronius_power_flow_0_http_fronius",
        1101.70,
    )
    assert_state(
        "sensor.energy_total_fronius_power_flow_0_http_fronius",
        44188000,
    )
    assert_state(
        "sensor.energy_year_fronius_power_flow_0_http_fronius",
        25508788,
    )
    assert_state(
        "sensor.power_battery_fronius_power_flow_0_http_fronius",
        STATE_UNKNOWN,
    )
    assert_state(
        "sensor.power_grid_fronius_power_flow_0_http_fronius",
        1703.74,
    )
    assert_state(
        "sensor.power_load_fronius_power_flow_0_http_fronius",
        -2814.74,
    )
    assert_state(
        "sensor.power_photovoltaics_fronius_power_flow_0_http_fronius",
        1111,
    )
    assert_state(
        "sensor.relative_autonomy_fronius_power_flow_0_http_fronius",
        39.47,
    )
    assert_state(
        "sensor.relative_self_consumption_fronius_power_flow_0_http_fronius",
        100,
    )
