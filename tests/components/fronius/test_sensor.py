"""Tests for the Fronius sensor platform."""
from homeassistant.components.fronius.coordinator import (
    FroniusInverterUpdateCoordinator,
    FroniusMeterUpdateCoordinator,
    FroniusPowerFlowUpdateCoordinator,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.const import STATE_UNKNOWN
from homeassistant.util import dt

from . import enable_all_entities, mock_responses, setup_fronius_integration

from tests.common import async_fire_time_changed


async def test_symo_inverter(hass, aioclient_mock):
    """Test Fronius Symo inverter entities."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state.state == str(expected_state)

    # Init at night
    mock_responses(aioclient_mock, night=True)
    config_entry = await setup_fronius_integration(hass)

    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 23
    await enable_all_entities(
        hass, config_entry.entry_id, FroniusInverterUpdateCoordinator.default_interval
    )
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 55
    assert_state("sensor.current_dc_fronius_inverter_1_http_fronius", 0)
    assert_state("sensor.energy_day_fronius_inverter_1_http_fronius", 10828)
    assert_state("sensor.energy_total_fronius_inverter_1_http_fronius", 44186900)
    assert_state("sensor.energy_year_fronius_inverter_1_http_fronius", 25507686)
    assert_state("sensor.voltage_dc_fronius_inverter_1_http_fronius", 16)

    # Second test at daytime when inverter is producing
    mock_responses(aioclient_mock, night=False)
    async_fire_time_changed(
        hass, dt.utcnow() + FroniusInverterUpdateCoordinator.default_interval
    )
    await hass.async_block_till_done()
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 57
    await enable_all_entities(
        hass, config_entry.entry_id, FroniusInverterUpdateCoordinator.default_interval
    )
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 59
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

    # Third test at nighttime - additional AC entities aren't changed
    mock_responses(aioclient_mock, night=True)
    async_fire_time_changed(
        hass, dt.utcnow() + FroniusInverterUpdateCoordinator.default_interval
    )
    await hass.async_block_till_done()
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
    await setup_fronius_integration(hass)
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 25

    # ignored constant entities:
    # hardware_platform, hardware_version, product_type
    # software_version, time_zone, time_zone_location
    # time_stamp, unique_identifier, utc_offset
    #
    # states are rounded to 4 decimals
    assert_state(
        "sensor.cash_factor_fronius_logger_info_0_http_fronius",
        0.078,
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
    config_entry = await setup_fronius_integration(hass)

    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 25
    await enable_all_entities(
        hass, config_entry.entry_id, FroniusMeterUpdateCoordinator.default_interval
    )
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 59
    # ignored entities:
    # manufacturer, model, serial, enable, timestamp, visible, meter_location
    #
    # states are rounded to 4 decimals
    assert_state("sensor.current_ac_phase_1_fronius_meter_0_http_fronius", 7.755)
    assert_state("sensor.current_ac_phase_2_fronius_meter_0_http_fronius", 6.68)
    assert_state("sensor.current_ac_phase_3_fronius_meter_0_http_fronius", 10.102)
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
    assert_state("sensor.power_apparent_phase_1_fronius_meter_0_http_fronius", 1772.793)
    assert_state("sensor.power_apparent_phase_2_fronius_meter_0_http_fronius", 1527.048)
    assert_state("sensor.power_apparent_phase_3_fronius_meter_0_http_fronius", 2333.562)
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
    config_entry = await setup_fronius_integration(hass)

    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 23
    await enable_all_entities(
        hass, config_entry.entry_id, FroniusInverterUpdateCoordinator.default_interval
    )
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 55
    # ignored: location, mode, timestamp
    #
    # states are rounded to 4 decimals
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
    async_fire_time_changed(
        hass, dt.utcnow() + FroniusPowerFlowUpdateCoordinator.default_interval
    )
    await hass.async_block_till_done()
    # still 55 because power_flow update interval is shorter than others
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 55
    assert_state(
        "sensor.energy_day_fronius_power_flow_0_http_fronius",
        1101.7001,
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
        39.4708,
    )
    assert_state(
        "sensor.relative_self_consumption_fronius_power_flow_0_http_fronius",
        100,
    )


async def test_gen24(hass, aioclient_mock):
    """Test Fronius Gen24 inverter entities."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == str(expected_state)

    mock_responses(aioclient_mock, fixture_set="gen24")
    config_entry = await setup_fronius_integration(hass, is_logger=False)

    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 25
    await enable_all_entities(
        hass, config_entry.entry_id, FroniusMeterUpdateCoordinator.default_interval
    )
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 57
    # inverter 1
    assert_state("sensor.energy_year_fronius_inverter_1_http_fronius", STATE_UNKNOWN)
    assert_state("sensor.current_ac_fronius_inverter_1_http_fronius", 0.1589)
    assert_state("sensor.current_dc_2_fronius_inverter_1_http_fronius", 0.0754)
    assert_state("sensor.status_code_fronius_inverter_1_http_fronius", 7)
    assert_state("sensor.energy_day_fronius_inverter_1_http_fronius", STATE_UNKNOWN)
    assert_state("sensor.current_dc_fronius_inverter_1_http_fronius", 0.0783)
    assert_state("sensor.voltage_dc_2_fronius_inverter_1_http_fronius", 403.4312)
    assert_state("sensor.power_ac_fronius_inverter_1_http_fronius", 37.3204)
    assert_state("sensor.error_code_fronius_inverter_1_http_fronius", 0)
    assert_state("sensor.voltage_dc_fronius_inverter_1_http_fronius", 411.3811)
    assert_state("sensor.energy_total_fronius_inverter_1_http_fronius", 1530193.42)
    assert_state("sensor.inverter_state_fronius_inverter_1_http_fronius", "Running")
    assert_state("sensor.voltage_ac_fronius_inverter_1_http_fronius", 234.9168)
    assert_state("sensor.frequency_ac_fronius_inverter_1_http_fronius", 49.9917)
    # meter
    assert_state("sensor.energy_real_produced_fronius_meter_0_http_fronius", 3863340.0)
    assert_state("sensor.energy_real_consumed_fronius_meter_0_http_fronius", 2013105.0)
    assert_state("sensor.power_real_fronius_meter_0_http_fronius", 653.1)
    assert_state("sensor.frequency_phase_average_fronius_meter_0_http_fronius", 49.9)
    assert_state("sensor.meter_location_fronius_meter_0_http_fronius", 0.0)
    assert_state("sensor.power_factor_fronius_meter_0_http_fronius", 0.828)
    assert_state(
        "sensor.energy_reactive_ac_consumed_fronius_meter_0_http_fronius", 88221.0
    )
    assert_state("sensor.energy_real_ac_minus_fronius_meter_0_http_fronius", 3863340.0)
    assert_state("sensor.current_ac_phase_2_fronius_meter_0_http_fronius", 2.33)
    assert_state("sensor.voltage_ac_phase_1_fronius_meter_0_http_fronius", 235.9)
    assert_state(
        "sensor.voltage_ac_phase_to_phase_12_fronius_meter_0_http_fronius", 408.7
    )
    assert_state("sensor.power_real_phase_2_fronius_meter_0_http_fronius", 294.9)
    assert_state("sensor.energy_real_ac_plus_fronius_meter_0_http_fronius", 2013105.0)
    assert_state("sensor.voltage_ac_phase_2_fronius_meter_0_http_fronius", 236.1)
    assert_state(
        "sensor.energy_reactive_ac_produced_fronius_meter_0_http_fronius", 1989125.0
    )
    assert_state("sensor.voltage_ac_phase_3_fronius_meter_0_http_fronius", 236.9)
    assert_state("sensor.power_factor_phase_1_fronius_meter_0_http_fronius", 0.441)
    assert_state(
        "sensor.voltage_ac_phase_to_phase_23_fronius_meter_0_http_fronius", 409.6
    )
    assert_state("sensor.current_ac_phase_3_fronius_meter_0_http_fronius", 1.825)
    assert_state("sensor.power_factor_phase_3_fronius_meter_0_http_fronius", 0.832)
    assert_state("sensor.power_apparent_phase_1_fronius_meter_0_http_fronius", 243.3)
    assert_state(
        "sensor.voltage_ac_phase_to_phase_31_fronius_meter_0_http_fronius", 409.4
    )
    assert_state("sensor.power_apparent_phase_2_fronius_meter_0_http_fronius", 323.4)
    assert_state("sensor.power_apparent_phase_3_fronius_meter_0_http_fronius", 301.2)
    assert_state("sensor.power_real_phase_1_fronius_meter_0_http_fronius", 106.8)
    assert_state("sensor.power_factor_phase_2_fronius_meter_0_http_fronius", 0.934)
    assert_state("sensor.power_real_phase_3_fronius_meter_0_http_fronius", 251.3)
    assert_state("sensor.power_reactive_phase_1_fronius_meter_0_http_fronius", -218.6)
    assert_state("sensor.power_reactive_phase_2_fronius_meter_0_http_fronius", -132.8)
    assert_state("sensor.power_reactive_phase_3_fronius_meter_0_http_fronius", -166.0)
    assert_state("sensor.power_apparent_fronius_meter_0_http_fronius", 868.0)
    assert_state("sensor.power_reactive_fronius_meter_0_http_fronius", -517.4)
    assert_state("sensor.current_ac_phase_1_fronius_meter_0_http_fronius", 1.145)
    # power_flow
    assert_state("sensor.power_grid_fronius_power_flow_0_http_fronius", 658.4)
    assert_state(
        "sensor.relative_self_consumption_fronius_power_flow_0_http_fronius", 100.0
    )
    assert_state(
        "sensor.power_photovoltaics_fronius_power_flow_0_http_fronius", 62.9481
    )
    assert_state("sensor.power_load_fronius_power_flow_0_http_fronius", -695.6827)
    assert_state("sensor.meter_mode_fronius_power_flow_0_http_fronius", "meter")
    assert_state("sensor.relative_autonomy_fronius_power_flow_0_http_fronius", 5.3592)
    assert_state(
        "sensor.power_battery_fronius_power_flow_0_http_fronius", STATE_UNKNOWN
    )
    assert_state("sensor.energy_year_fronius_power_flow_0_http_fronius", STATE_UNKNOWN)
    assert_state("sensor.energy_day_fronius_power_flow_0_http_fronius", STATE_UNKNOWN)
    assert_state("sensor.energy_total_fronius_power_flow_0_http_fronius", 1530193.42)


async def test_gen24_storage(hass, aioclient_mock):
    """Test Fronius Gen24 inverter with BYD battery and Ohmpilot entities."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == str(expected_state)

    mock_responses(aioclient_mock, fixture_set="gen24_storage")
    config_entry = await setup_fronius_integration(hass, is_logger=False)

    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 31
    await enable_all_entities(
        hass, config_entry.entry_id, FroniusMeterUpdateCoordinator.default_interval
    )
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 63
    # inverter 1
    assert_state("sensor.current_dc_fronius_inverter_1_http_fronius", 0.3952)
    assert_state("sensor.voltage_dc_2_fronius_inverter_1_http_fronius", 318.8103)
    assert_state("sensor.current_dc_2_fronius_inverter_1_http_fronius", 0.3564)
    assert_state("sensor.energy_year_fronius_inverter_1_http_fronius", STATE_UNKNOWN)
    assert_state("sensor.current_ac_fronius_inverter_1_http_fronius", 1.1087)
    assert_state("sensor.power_ac_fronius_inverter_1_http_fronius", 250.9093)
    assert_state("sensor.energy_day_fronius_inverter_1_http_fronius", STATE_UNKNOWN)
    assert_state("sensor.error_code_fronius_inverter_1_http_fronius", 0)
    assert_state("sensor.status_code_fronius_inverter_1_http_fronius", 7)
    assert_state("sensor.energy_total_fronius_inverter_1_http_fronius", 7512794.0117)
    assert_state("sensor.inverter_state_fronius_inverter_1_http_fronius", "Running")
    assert_state("sensor.voltage_dc_fronius_inverter_1_http_fronius", 419.1009)
    assert_state("sensor.voltage_ac_fronius_inverter_1_http_fronius", 227.354)
    assert_state("sensor.frequency_ac_fronius_inverter_1_http_fronius", 49.9816)
    # meter
    assert_state("sensor.energy_real_produced_fronius_meter_0_http_fronius", 1705128.0)
    assert_state("sensor.power_real_fronius_meter_0_http_fronius", 487.7)
    assert_state("sensor.power_factor_fronius_meter_0_http_fronius", 0.698)
    assert_state("sensor.energy_real_consumed_fronius_meter_0_http_fronius", 1247204.0)
    assert_state("sensor.frequency_phase_average_fronius_meter_0_http_fronius", 49.9)
    assert_state("sensor.meter_location_fronius_meter_0_http_fronius", 0.0)
    assert_state("sensor.power_reactive_fronius_meter_0_http_fronius", -501.5)
    assert_state(
        "sensor.energy_reactive_ac_produced_fronius_meter_0_http_fronius", 3266105.0
    )
    assert_state("sensor.power_real_phase_3_fronius_meter_0_http_fronius", 19.6)
    assert_state("sensor.current_ac_phase_3_fronius_meter_0_http_fronius", 0.645)
    assert_state("sensor.energy_real_ac_minus_fronius_meter_0_http_fronius", 1705128.0)
    assert_state("sensor.power_apparent_phase_2_fronius_meter_0_http_fronius", 383.9)
    assert_state("sensor.current_ac_phase_1_fronius_meter_0_http_fronius", 1.701)
    assert_state("sensor.current_ac_phase_2_fronius_meter_0_http_fronius", 1.832)
    assert_state("sensor.power_apparent_phase_1_fronius_meter_0_http_fronius", 319.5)
    assert_state("sensor.voltage_ac_phase_1_fronius_meter_0_http_fronius", 229.4)
    assert_state("sensor.power_real_phase_2_fronius_meter_0_http_fronius", 150.0)
    assert_state(
        "sensor.voltage_ac_phase_to_phase_31_fronius_meter_0_http_fronius", 394.3
    )
    assert_state("sensor.voltage_ac_phase_2_fronius_meter_0_http_fronius", 225.6)
    assert_state(
        "sensor.energy_reactive_ac_consumed_fronius_meter_0_http_fronius", 5482.0
    )
    assert_state("sensor.energy_real_ac_plus_fronius_meter_0_http_fronius", 1247204.0)
    assert_state("sensor.power_factor_phase_1_fronius_meter_0_http_fronius", 0.995)
    assert_state("sensor.power_factor_phase_3_fronius_meter_0_http_fronius", 0.163)
    assert_state("sensor.power_factor_phase_2_fronius_meter_0_http_fronius", 0.389)
    assert_state("sensor.power_reactive_phase_1_fronius_meter_0_http_fronius", -31.3)
    assert_state("sensor.power_reactive_phase_3_fronius_meter_0_http_fronius", -116.7)
    assert_state(
        "sensor.voltage_ac_phase_to_phase_12_fronius_meter_0_http_fronius", 396.0
    )
    assert_state(
        "sensor.voltage_ac_phase_to_phase_23_fronius_meter_0_http_fronius", 393.0
    )
    assert_state("sensor.power_reactive_phase_2_fronius_meter_0_http_fronius", -353.4)
    assert_state("sensor.power_real_phase_1_fronius_meter_0_http_fronius", 317.9)
    assert_state("sensor.voltage_ac_phase_3_fronius_meter_0_http_fronius", 228.3)
    assert_state("sensor.power_apparent_fronius_meter_0_http_fronius", 821.9)
    assert_state("sensor.power_apparent_phase_3_fronius_meter_0_http_fronius", 118.4)
    # power_flow
    assert_state("sensor.power_grid_fronius_power_flow_0_http_fronius", 2274.9)
    assert_state("sensor.power_battery_fronius_power_flow_0_http_fronius", 0.1591)
    assert_state("sensor.power_load_fronius_power_flow_0_http_fronius", -2459.3092)
    assert_state(
        "sensor.relative_self_consumption_fronius_power_flow_0_http_fronius", 100.0
    )
    assert_state(
        "sensor.power_photovoltaics_fronius_power_flow_0_http_fronius", 216.4328
    )
    assert_state("sensor.relative_autonomy_fronius_power_flow_0_http_fronius", 7.4984)
    assert_state("sensor.meter_mode_fronius_power_flow_0_http_fronius", "bidirectional")
    assert_state("sensor.energy_year_fronius_power_flow_0_http_fronius", STATE_UNKNOWN)
    assert_state("sensor.energy_day_fronius_power_flow_0_http_fronius", STATE_UNKNOWN)
    assert_state("sensor.energy_total_fronius_power_flow_0_http_fronius", 7512664.4042)
    # storage
    assert_state("sensor.current_dc_fronius_storage_0_http_fronius", 0.0)
    assert_state("sensor.state_of_charge_fronius_storage_0_http_fronius", 4.6)
    assert_state("sensor.capacity_maximum_fronius_storage_0_http_fronius", 16588)
    assert_state("sensor.temperature_cell_fronius_storage_0_http_fronius", 21.5)
    assert_state("sensor.capacity_designed_fronius_storage_0_http_fronius", 16588)
    assert_state("sensor.voltage_dc_fronius_storage_0_http_fronius", 0.0)
