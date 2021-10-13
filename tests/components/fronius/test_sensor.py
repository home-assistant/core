"""Tests for the Fronius sensor platform."""

from homeassistant.components.fronius.sensor import DEFAULT_SCAN_INTERVAL
from homeassistant.const import STATE_UNKNOWN
from homeassistant.util import dt

from . import setup_fronius_integration
from .responses import symo

from tests.common import async_fire_time_changed


async def test_symo_inverter(hass, aioclient_mock):
    """Test Fronius Symo inverter entities."""
    async_fire_time_changed(hass, dt.utcnow())

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state.state == str(expected_state)

    aioclient_mock.get(
        url=symo.APIVersion.url,
        json=symo.APIVersion.json,
    )
    # Init at night
    aioclient_mock.get(
        url=symo.InverterDevice.url,
        json=symo.InverterDevice.json_night,
    )
    await setup_fronius_integration(hass, aioclient_mock, [symo.InverterDevice.config])

    assert len(hass.states.async_all()) == 10
    # 5 ignored from DeviceStatus
    assert_state("sensor.current_dc_fronius_inverter_1_http_fronius", 0)
    assert_state("sensor.energy_day_fronius_inverter_1_http_fronius", 10828)
    assert_state("sensor.energy_total_fronius_inverter_1_http_fronius", 44186900)
    assert_state("sensor.energy_year_fronius_inverter_1_http_fronius", 25507686)
    assert_state("sensor.voltage_dc_fronius_inverter_1_http_fronius", 16)

    # Second test at daytime when inverter is producing
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        url=symo.InverterDevice.url,
        json=symo.InverterDevice.json_day,
    )
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

    aioclient_mock.get(
        url=symo.APIVersion.url,
        json=symo.APIVersion.json,
    )
    aioclient_mock.get(
        url=symo.LoggerInfo.url,
        json=symo.LoggerInfo.json,
    )
    await setup_fronius_integration(hass, aioclient_mock, [symo.LoggerInfo.config])

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

    aioclient_mock.get(
        url=symo.APIVersion.url,
        json=symo.APIVersion.json,
    )
    aioclient_mock.get(
        url=symo.MeterDevice.url,
        json=symo.MeterDevice.json,
    )
    await setup_fronius_integration(hass, aioclient_mock, [symo.MeterDevice.config])

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

    aioclient_mock.get(
        url=symo.APIVersion.url,
        json=symo.APIVersion.json,
    )
    # First test at night
    aioclient_mock.get(
        url=symo.PowerFlow.url,
        json=symo.PowerFlow.json_night,
    )
    await setup_fronius_integration(hass, aioclient_mock, [symo.PowerFlow.config])

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
    aioclient_mock.clear_requests()
    aioclient_mock.get(
        url=symo.PowerFlow.url,
        json=symo.PowerFlow.json_day,
    )
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
