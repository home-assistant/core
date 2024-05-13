"""Tests for the Fronius sensor platform."""

from freezegun.api import FrozenDateTimeFactory

from homeassistant.components.fronius.const import DOMAIN
from homeassistant.components.fronius.coordinator import (
    FroniusInverterUpdateCoordinator,
    FroniusMeterUpdateCoordinator,
    FroniusPowerFlowUpdateCoordinator,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import enable_all_entities, mock_responses, setup_fronius_integration

from tests.common import async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker


async def test_symo_inverter(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Fronius Symo inverter entities."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state.state == str(expected_state)

    # Init at night
    mock_responses(aioclient_mock, night=True)
    config_entry = await setup_fronius_integration(hass)

    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 20
    await enable_all_entities(
        hass,
        freezer,
        config_entry.entry_id,
        FroniusInverterUpdateCoordinator.default_interval,
    )
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 52
    assert_state("sensor.symo_20_dc_current", 0)
    assert_state("sensor.symo_20_energy_day", 10828)
    assert_state("sensor.symo_20_total_energy", 44186900)
    assert_state("sensor.symo_20_energy_year", 25507686)
    assert_state("sensor.symo_20_dc_voltage", 16)

    # Second test at daytime when inverter is producing
    mock_responses(aioclient_mock, night=False)
    freezer.tick(FroniusInverterUpdateCoordinator.default_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 56
    await enable_all_entities(
        hass,
        freezer,
        config_entry.entry_id,
        FroniusInverterUpdateCoordinator.default_interval,
    )
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 58
    # 4 additional AC entities
    assert_state("sensor.symo_20_dc_current", 2.19)
    assert_state("sensor.symo_20_energy_day", 1113)
    assert_state("sensor.symo_20_total_energy", 44188000)
    assert_state("sensor.symo_20_energy_year", 25508798)
    assert_state("sensor.symo_20_dc_voltage", 518)
    assert_state("sensor.symo_20_ac_current", 5.19)
    assert_state("sensor.symo_20_frequency", 49.94)
    assert_state("sensor.symo_20_ac_power", 1190)
    assert_state("sensor.symo_20_ac_voltage", 227.90)

    # Third test at nighttime - additional AC entities default to 0
    mock_responses(aioclient_mock, night=True)
    freezer.tick(FroniusInverterUpdateCoordinator.default_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert_state("sensor.symo_20_ac_current", 0)
    assert_state("sensor.symo_20_frequency", 0)
    assert_state("sensor.symo_20_ac_power", 0)
    assert_state("sensor.symo_20_ac_voltage", 0)


async def test_symo_logger(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test Fronius Symo logger entities."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == str(expected_state)

    mock_responses(aioclient_mock)
    await setup_fronius_integration(hass)
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 24
    # states are rounded to 4 decimals
    assert_state("sensor.solarnet_grid_export_tariff", 0.078)
    assert_state("sensor.solarnet_co2_factor", 0.53)
    assert_state("sensor.solarnet_grid_import_tariff", 0.15)


async def test_symo_meter(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Fronius Symo meter entities."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == str(expected_state)

    mock_responses(aioclient_mock)
    config_entry = await setup_fronius_integration(hass)

    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 24
    await enable_all_entities(
        hass,
        freezer,
        config_entry.entry_id,
        FroniusMeterUpdateCoordinator.default_interval,
    )
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 58
    # states are rounded to 4 decimals
    assert_state("sensor.smart_meter_63a_current_phase_1", 7.755)
    assert_state("sensor.smart_meter_63a_current_phase_2", 6.68)
    assert_state("sensor.smart_meter_63a_current_phase_3", 10.102)
    assert_state("sensor.smart_meter_63a_reactive_energy_consumed", 59960790)
    assert_state("sensor.smart_meter_63a_reactive_energy_produced", 723160)
    assert_state("sensor.smart_meter_63a_real_energy_minus", 35623065)
    assert_state("sensor.smart_meter_63a_real_energy_plus", 15303334)
    assert_state("sensor.smart_meter_63a_real_energy_consumed", 15303334)
    assert_state("sensor.smart_meter_63a_real_energy_produced", 35623065)
    assert_state("sensor.smart_meter_63a_frequency_phase_average", 50)
    assert_state("sensor.smart_meter_63a_apparent_power_phase_1", 1772.793)
    assert_state("sensor.smart_meter_63a_apparent_power_phase_2", 1527.048)
    assert_state("sensor.smart_meter_63a_apparent_power_phase_3", 2333.562)
    assert_state("sensor.smart_meter_63a_apparent_power", 5592.57)
    assert_state("sensor.smart_meter_63a_power_factor_phase_1", -0.99)
    assert_state("sensor.smart_meter_63a_power_factor_phase_2", -0.99)
    assert_state("sensor.smart_meter_63a_power_factor_phase_3", 0.99)
    assert_state("sensor.smart_meter_63a_power_factor", 1)
    assert_state("sensor.smart_meter_63a_reactive_power_phase_1", 51.48)
    assert_state("sensor.smart_meter_63a_reactive_power_phase_2", 115.63)
    assert_state("sensor.smart_meter_63a_reactive_power_phase_3", -164.24)
    assert_state("sensor.smart_meter_63a_reactive_power", 2.87)
    assert_state("sensor.smart_meter_63a_real_power_phase_1", 1765.55)
    assert_state("sensor.smart_meter_63a_real_power_phase_2", 1515.8)
    assert_state("sensor.smart_meter_63a_real_power_phase_3", 2311.22)
    assert_state("sensor.smart_meter_63a_real_power", 5592.57)
    assert_state("sensor.smart_meter_63a_voltage_phase_1", 228.6)
    assert_state("sensor.smart_meter_63a_voltage_phase_2", 228.6)
    assert_state("sensor.smart_meter_63a_voltage_phase_3", 231)
    assert_state("sensor.smart_meter_63a_voltage_phase_1_2", 395.9)
    assert_state("sensor.smart_meter_63a_voltage_phase_2_3", 398)
    assert_state("sensor.smart_meter_63a_voltage_phase_3_1", 398)


async def test_symo_power_flow(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Fronius Symo power flow entities."""
    async_fire_time_changed(hass)

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state.state == str(expected_state)

    # First test at night
    mock_responses(aioclient_mock, night=True)
    config_entry = await setup_fronius_integration(hass)

    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 20
    await enable_all_entities(
        hass,
        freezer,
        config_entry.entry_id,
        FroniusInverterUpdateCoordinator.default_interval,
    )
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 52
    # states are rounded to 4 decimals
    assert_state("sensor.solarnet_energy_day", 10828)
    assert_state("sensor.solarnet_total_energy", 44186900)
    assert_state("sensor.solarnet_energy_year", 25507686)
    assert_state("sensor.solarnet_power_grid", 975.31)
    assert_state("sensor.solarnet_power_load", -975.31)
    assert_state("sensor.solarnet_relative_autonomy", 0)

    # Second test at daytime when inverter is producing
    mock_responses(aioclient_mock, night=False)
    freezer.tick(FroniusPowerFlowUpdateCoordinator.default_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    # 54 because power_flow `rel_SelfConsumption` and `P_PV` is not `null` anymore
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 54
    assert_state("sensor.solarnet_energy_day", 1101.7001)
    assert_state("sensor.solarnet_total_energy", 44188000)
    assert_state("sensor.solarnet_energy_year", 25508788)
    assert_state("sensor.solarnet_power_grid", 1703.74)
    assert_state("sensor.solarnet_power_load", -2814.74)
    assert_state("sensor.solarnet_power_photovoltaics", 1111)
    assert_state("sensor.solarnet_relative_autonomy", 39.4708)
    assert_state("sensor.solarnet_relative_self_consumption", 100)

    # Third test at nighttime - default values are used
    mock_responses(aioclient_mock, night=True)
    freezer.tick(FroniusPowerFlowUpdateCoordinator.default_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 54
    assert_state("sensor.solarnet_energy_day", 10828)
    assert_state("sensor.solarnet_total_energy", 44186900)
    assert_state("sensor.solarnet_energy_year", 25507686)
    assert_state("sensor.solarnet_power_grid", 975.31)
    assert_state("sensor.solarnet_power_load", -975.31)
    assert_state("sensor.solarnet_power_photovoltaics", 0)
    assert_state("sensor.solarnet_relative_autonomy", 0)
    assert_state("sensor.solarnet_relative_self_consumption", 0)


async def test_gen24(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Fronius Gen24 inverter entities."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == str(expected_state)

    mock_responses(aioclient_mock, fixture_set="gen24")
    config_entry = await setup_fronius_integration(hass, is_logger=False)

    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 22
    await enable_all_entities(
        hass,
        freezer,
        config_entry.entry_id,
        FroniusMeterUpdateCoordinator.default_interval,
    )
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 52
    # inverter 1
    assert_state("sensor.inverter_name_ac_current", 0.1589)
    assert_state("sensor.inverter_name_dc_current_2", 0.0754)
    assert_state("sensor.inverter_name_status_code", 7)
    assert_state("sensor.inverter_name_dc_current", 0.0783)
    assert_state("sensor.inverter_name_dc_voltage_2", 403.4312)
    assert_state("sensor.inverter_name_ac_power", 37.3204)
    assert_state("sensor.inverter_name_error_code", 0)
    assert_state("sensor.inverter_name_dc_voltage", 411.3811)
    assert_state("sensor.inverter_name_total_energy", 1530193.42)
    assert_state("sensor.inverter_name_inverter_state", "Running")
    assert_state("sensor.inverter_name_ac_voltage", 234.9168)
    assert_state("sensor.inverter_name_frequency", 49.9917)
    # meter
    assert_state("sensor.smart_meter_ts_65a_3_real_energy_produced", 3863340.0)
    assert_state("sensor.smart_meter_ts_65a_3_real_energy_consumed", 2013105.0)
    assert_state("sensor.smart_meter_ts_65a_3_real_power", 653.1)
    assert_state("sensor.smart_meter_ts_65a_3_frequency_phase_average", 49.9)
    assert_state("sensor.smart_meter_ts_65a_3_meter_location", 0.0)
    assert_state("sensor.smart_meter_ts_65a_3_power_factor", 0.828)
    assert_state("sensor.smart_meter_ts_65a_3_reactive_energy_consumed", 88221.0)
    assert_state("sensor.smart_meter_ts_65a_3_real_energy_minus", 3863340.0)
    assert_state("sensor.smart_meter_ts_65a_3_current_phase_2", 2.33)
    assert_state("sensor.smart_meter_ts_65a_3_voltage_phase_1", 235.9)
    assert_state("sensor.smart_meter_ts_65a_3_voltage_phase_1_2", 408.7)
    assert_state("sensor.smart_meter_ts_65a_3_real_power_phase_2", 294.9)
    assert_state("sensor.smart_meter_ts_65a_3_real_energy_plus", 2013105.0)
    assert_state("sensor.smart_meter_ts_65a_3_voltage_phase_2", 236.1)
    assert_state("sensor.smart_meter_ts_65a_3_reactive_energy_produced", 1989125.0)
    assert_state("sensor.smart_meter_ts_65a_3_voltage_phase_3", 236.9)
    assert_state("sensor.smart_meter_ts_65a_3_power_factor_phase_1", 0.441)
    assert_state("sensor.smart_meter_ts_65a_3_voltage_phase_2_3", 409.6)
    assert_state("sensor.smart_meter_ts_65a_3_current_phase_3", 1.825)
    assert_state("sensor.smart_meter_ts_65a_3_power_factor_phase_3", 0.832)
    assert_state("sensor.smart_meter_ts_65a_3_apparent_power_phase_1", 243.3)
    assert_state("sensor.smart_meter_ts_65a_3_voltage_phase_3_1", 409.4)
    assert_state("sensor.smart_meter_ts_65a_3_apparent_power_phase_2", 323.4)
    assert_state("sensor.smart_meter_ts_65a_3_apparent_power_phase_3", 301.2)
    assert_state("sensor.smart_meter_ts_65a_3_real_power_phase_1", 106.8)
    assert_state("sensor.smart_meter_ts_65a_3_power_factor_phase_2", 0.934)
    assert_state("sensor.smart_meter_ts_65a_3_real_power_phase_3", 251.3)
    assert_state("sensor.smart_meter_ts_65a_3_reactive_power_phase_1", -218.6)
    assert_state("sensor.smart_meter_ts_65a_3_reactive_power_phase_2", -132.8)
    assert_state("sensor.smart_meter_ts_65a_3_reactive_power_phase_3", -166.0)
    assert_state("sensor.smart_meter_ts_65a_3_apparent_power", 868.0)
    assert_state("sensor.smart_meter_ts_65a_3_reactive_power", -517.4)
    assert_state("sensor.smart_meter_ts_65a_3_current_phase_1", 1.145)
    # power_flow
    assert_state("sensor.solarnet_power_grid", 658.4)
    assert_state("sensor.solarnet_relative_self_consumption", 100.0)
    assert_state("sensor.solarnet_power_photovoltaics", 62.9481)
    assert_state("sensor.solarnet_power_load", -695.6827)
    assert_state("sensor.solarnet_meter_mode", "meter")
    assert_state("sensor.solarnet_relative_autonomy", 5.3592)
    assert_state("sensor.solarnet_total_energy", 1530193.42)


async def test_gen24_storage(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Fronius Gen24 inverter with BYD battery and Ohmpilot entities."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == str(expected_state)

    mock_responses(aioclient_mock, fixture_set="gen24_storage")
    config_entry = await setup_fronius_integration(
        hass, is_logger=False, unique_id="12345678"
    )

    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 34
    await enable_all_entities(
        hass,
        freezer,
        config_entry.entry_id,
        FroniusMeterUpdateCoordinator.default_interval,
    )
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 64
    # inverter 1
    assert_state("sensor.gen24_storage_dc_current", 0.3952)
    assert_state("sensor.gen24_storage_dc_voltage_2", 318.8103)
    assert_state("sensor.gen24_storage_dc_current_2", 0.3564)
    assert_state("sensor.gen24_storage_ac_current", 1.1087)
    assert_state("sensor.gen24_storage_ac_power", 250.9093)
    assert_state("sensor.gen24_storage_error_code", 0)
    assert_state("sensor.gen24_storage_status_code", 7)
    assert_state("sensor.gen24_storage_total_energy", 7512794.0117)
    assert_state("sensor.gen24_storage_inverter_state", "Running")
    assert_state("sensor.gen24_storage_dc_voltage", 419.1009)
    assert_state("sensor.gen24_storage_ac_voltage", 227.354)
    assert_state("sensor.gen24_storage_frequency", 49.9816)
    # meter
    assert_state("sensor.smart_meter_ts_65a_3_real_energy_produced", 1705128.0)
    assert_state("sensor.smart_meter_ts_65a_3_real_power", 487.7)
    assert_state("sensor.smart_meter_ts_65a_3_power_factor", 0.698)
    assert_state("sensor.smart_meter_ts_65a_3_real_energy_consumed", 1247204.0)
    assert_state("sensor.smart_meter_ts_65a_3_frequency_phase_average", 49.9)
    assert_state("sensor.smart_meter_ts_65a_3_meter_location", 0.0)
    assert_state("sensor.smart_meter_ts_65a_3_reactive_power", -501.5)
    assert_state("sensor.smart_meter_ts_65a_3_reactive_energy_produced", 3266105.0)
    assert_state("sensor.smart_meter_ts_65a_3_real_power_phase_3", 19.6)
    assert_state("sensor.smart_meter_ts_65a_3_current_phase_3", 0.645)
    assert_state("sensor.smart_meter_ts_65a_3_real_energy_minus", 1705128.0)
    assert_state("sensor.smart_meter_ts_65a_3_apparent_power_phase_2", 383.9)
    assert_state("sensor.smart_meter_ts_65a_3_current_phase_1", 1.701)
    assert_state("sensor.smart_meter_ts_65a_3_current_phase_2", 1.832)
    assert_state("sensor.smart_meter_ts_65a_3_apparent_power_phase_1", 319.5)
    assert_state("sensor.smart_meter_ts_65a_3_voltage_phase_1", 229.4)
    assert_state("sensor.smart_meter_ts_65a_3_real_power_phase_2", 150.0)
    assert_state("sensor.smart_meter_ts_65a_3_voltage_phase_3_1", 394.3)
    assert_state("sensor.smart_meter_ts_65a_3_voltage_phase_2", 225.6)
    assert_state("sensor.smart_meter_ts_65a_3_reactive_energy_consumed", 5482.0)
    assert_state("sensor.smart_meter_ts_65a_3_real_energy_plus", 1247204.0)
    assert_state("sensor.smart_meter_ts_65a_3_power_factor_phase_1", 0.995)
    assert_state("sensor.smart_meter_ts_65a_3_power_factor_phase_3", 0.163)
    assert_state("sensor.smart_meter_ts_65a_3_power_factor_phase_2", 0.389)
    assert_state("sensor.smart_meter_ts_65a_3_reactive_power_phase_1", -31.3)
    assert_state("sensor.smart_meter_ts_65a_3_reactive_power_phase_3", -116.7)
    assert_state("sensor.smart_meter_ts_65a_3_voltage_phase_1_2", 396.0)
    assert_state("sensor.smart_meter_ts_65a_3_voltage_phase_2_3", 393.0)
    assert_state("sensor.smart_meter_ts_65a_3_reactive_power_phase_2", -353.4)
    assert_state("sensor.smart_meter_ts_65a_3_real_power_phase_1", 317.9)
    assert_state("sensor.smart_meter_ts_65a_3_voltage_phase_3", 228.3)
    assert_state("sensor.smart_meter_ts_65a_3_apparent_power", 821.9)
    assert_state("sensor.smart_meter_ts_65a_3_apparent_power_phase_3", 118.4)
    # ohmpilot
    assert_state("sensor.ohmpilot_energy_consumed", 1233295.0)
    assert_state("sensor.ohmpilot_power", 0.0)
    assert_state("sensor.ohmpilot_temperature", 38.9)
    assert_state("sensor.ohmpilot_state_code", 0.0)
    assert_state("sensor.ohmpilot_state_message", "Up and running")
    # power_flow
    assert_state("sensor.solarnet_power_grid", 2274.9)
    assert_state("sensor.solarnet_power_battery", 0.1591)
    assert_state("sensor.solarnet_power_load", -2459.3092)
    assert_state("sensor.solarnet_relative_self_consumption", 100.0)
    assert_state("sensor.solarnet_power_photovoltaics", 216.4328)
    assert_state("sensor.solarnet_relative_autonomy", 7.4984)
    assert_state("sensor.solarnet_meter_mode", "bidirectional")
    assert_state("sensor.solarnet_total_energy", 7512664.4042)
    # storage
    assert_state("sensor.byd_battery_box_premium_hv_dc_current", 0.0)
    assert_state("sensor.byd_battery_box_premium_hv_state_of_charge", 4.6)
    assert_state("sensor.byd_battery_box_premium_hv_maximum_capacity", 16588)
    assert_state("sensor.byd_battery_box_premium_hv_temperature", 21.5)
    assert_state("sensor.byd_battery_box_premium_hv_designed_capacity", 16588)
    assert_state("sensor.byd_battery_box_premium_hv_dc_voltage", 0.0)

    # Devices
    device_registry = dr.async_get(hass)

    solar_net = device_registry.async_get_device(
        identifiers={(DOMAIN, "solar_net_12345678")}
    )
    assert solar_net.configuration_url == "http://fronius"
    assert solar_net.manufacturer == "Fronius"
    assert solar_net.name == "SolarNet"

    inverter_1 = device_registry.async_get_device(identifiers={(DOMAIN, "12345678")})
    assert inverter_1.manufacturer == "Fronius"
    assert inverter_1.model == "Gen24"
    assert inverter_1.name == "Gen24 Storage"

    meter = device_registry.async_get_device(identifiers={(DOMAIN, "1234567890")})
    assert meter.manufacturer == "Fronius"
    assert meter.model == "Smart Meter TS 65A-3"
    assert meter.name == "Smart Meter TS 65A-3"

    ohmpilot = device_registry.async_get_device(identifiers={(DOMAIN, "23456789")})
    assert ohmpilot.manufacturer == "Fronius"
    assert ohmpilot.model == "Ohmpilot 6"
    assert ohmpilot.name == "Ohmpilot"
    assert ohmpilot.sw_version == "1.0.25-3"

    storage = device_registry.async_get_device(
        identifiers={(DOMAIN, "P030T020Z2001234567     ")}
    )
    assert storage.manufacturer == "BYD"
    assert storage.model == "BYD Battery-Box Premium HV"
    assert storage.name == "BYD Battery-Box Premium HV"


async def test_primo_s0(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test Fronius Primo dual inverter with S0 meter entities."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == str(expected_state)

    mock_responses(aioclient_mock, fixture_set="primo_s0", inverter_ids=[1, 2])
    config_entry = await setup_fronius_integration(hass, is_logger=True)

    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 29
    await enable_all_entities(
        hass,
        freezer,
        config_entry.entry_id,
        FroniusMeterUpdateCoordinator.default_interval,
    )
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 40
    # logger
    assert_state("sensor.solarnet_grid_export_tariff", 1)
    assert_state("sensor.solarnet_co2_factor", 0.53)
    assert_state("sensor.solarnet_grid_import_tariff", 1)
    # inverter 1
    assert_state("sensor.primo_5_0_1_total_energy", 17114940)
    assert_state("sensor.primo_5_0_1_energy_day", 22504)
    assert_state("sensor.primo_5_0_1_dc_voltage", 452.3)
    assert_state("sensor.primo_5_0_1_ac_power", 862)
    assert_state("sensor.primo_5_0_1_error_code", 0)
    assert_state("sensor.primo_5_0_1_dc_current", 4.23)
    assert_state("sensor.primo_5_0_1_status_code", 7)
    assert_state("sensor.primo_5_0_1_energy_year", 7532755.5)
    assert_state("sensor.primo_5_0_1_ac_current", 3.85)
    assert_state("sensor.primo_5_0_1_ac_voltage", 223.9)
    assert_state("sensor.primo_5_0_1_frequency", 60)
    assert_state("sensor.primo_5_0_1_led_color", 2)
    assert_state("sensor.primo_5_0_1_led_state", 0)
    # inverter 2
    assert_state("sensor.primo_3_0_1_total_energy", 5796010)
    assert_state("sensor.primo_3_0_1_energy_day", 14237)
    assert_state("sensor.primo_3_0_1_dc_voltage", 329.5)
    assert_state("sensor.primo_3_0_1_ac_power", 296)
    assert_state("sensor.primo_3_0_1_error_code", 0)
    assert_state("sensor.primo_3_0_1_dc_current", 0.97)
    assert_state("sensor.primo_3_0_1_status_code", 7)
    assert_state("sensor.primo_3_0_1_energy_year", 3596193.25)
    assert_state("sensor.primo_3_0_1_ac_current", 1.32)
    assert_state("sensor.primo_3_0_1_ac_voltage", 223.6)
    assert_state("sensor.primo_3_0_1_frequency", 60.01)
    assert_state("sensor.primo_3_0_1_led_color", 2)
    assert_state("sensor.primo_3_0_1_led_state", 0)
    # meter
    assert_state("sensor.s0_meter_at_inverter_1_meter_location", 1)
    assert_state("sensor.s0_meter_at_inverter_1_real_power", -2216.7487)
    # power_flow
    assert_state("sensor.solarnet_power_load", -2218.9349)
    assert_state("sensor.solarnet_meter_mode", "vague-meter")
    assert_state("sensor.solarnet_power_photovoltaics", 1834)
    assert_state("sensor.solarnet_power_grid", 384.9349)
    assert_state("sensor.solarnet_relative_self_consumption", 100)
    assert_state("sensor.solarnet_relative_autonomy", 82.6523)
    assert_state("sensor.solarnet_total_energy", 22910919.5)
    assert_state("sensor.solarnet_energy_day", 36724)
    assert_state("sensor.solarnet_energy_year", 11128933.25)

    # Devices
    device_registry = dr.async_get(hass)

    solar_net = device_registry.async_get_device(
        identifiers={(DOMAIN, "solar_net_123.4567890")}
    )
    assert solar_net.configuration_url == "http://fronius"
    assert solar_net.manufacturer == "Fronius"
    assert solar_net.model == "fronius-datamanager-card"
    assert solar_net.name == "SolarNet"
    assert solar_net.sw_version == "3.18.7-1"

    inverter_1 = device_registry.async_get_device(identifiers={(DOMAIN, "123456")})
    assert inverter_1.manufacturer == "Fronius"
    assert inverter_1.model == "Primo 5.0-1"
    assert inverter_1.name == "Primo 5.0-1"

    inverter_2 = device_registry.async_get_device(identifiers={(DOMAIN, "234567")})
    assert inverter_2.manufacturer == "Fronius"
    assert inverter_2.model == "Primo 3.0-1"
    assert inverter_2.name == "Primo 3.0-1"

    meter = device_registry.async_get_device(
        identifiers={(DOMAIN, "solar_net_123.4567890:S0 Meter at inverter 1")}
    )
    assert meter.manufacturer == "Fronius"
    assert meter.model == "S0 Meter at inverter 1"
    assert meter.name == "S0 Meter at inverter 1"
