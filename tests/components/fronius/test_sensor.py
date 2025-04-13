"""Tests for the Fronius sensor platform."""

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.fronius.const import DOMAIN
from homeassistant.components.fronius.coordinator import (
    FroniusInverterUpdateCoordinator,
    FroniusPowerFlowUpdateCoordinator,
)
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import mock_responses, setup_fronius_integration

from tests.common import async_fire_time_changed, snapshot_platform
from tests.test_util.aiohttp import AiohttpClientMocker


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_symo_inverter(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Fronius Symo inverter entities."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state.state == str(expected_state)

    # Init at night
    mock_responses(aioclient_mock, night=True)
    await setup_fronius_integration(hass)

    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 59
    assert_state("sensor.symo_20_dc_current", 0)
    assert_state("sensor.symo_20_energy_day", 10828)
    assert_state("sensor.symo_20_total_energy", 44186900)
    assert_state("sensor.symo_20_energy_year", 25507686)
    assert_state("sensor.symo_20_dc_voltage", 16)
    assert_state("sensor.symo_20_status_message", "startup")

    # Second test at daytime when inverter is producing
    mock_responses(aioclient_mock, night=False)
    freezer.tick(FroniusInverterUpdateCoordinator.default_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 65
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
    assert_state("sensor.symo_20_status_message", "running")

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
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 26
    # states are rounded to 4 decimals
    assert_state("sensor.solarnet_grid_export_tariff", 0.078)
    assert_state("sensor.solarnet_co2_factor", 0.53)
    assert_state("sensor.solarnet_grid_import_tariff", 0.15)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
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
    await setup_fronius_integration(hass)

    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 65
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
    assert_state("sensor.smart_meter_63a_meter_location", 0)
    assert_state("sensor.smart_meter_63a_meter_location_description", "feed_in")


@pytest.mark.parametrize(
    ("location_code", "expected_code", "expected_description"),
    [
        (-1, -1, "unknown"),
        (3, 3, "external_generator"),
        (4, 4, "external_battery"),
        (7, 7, "unknown"),
        (256, 256, "subload"),
        (511, 511, "subload"),
        (512, 512, "unknown"),
    ],
)
async def test_symo_meter_forged(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    location_code: int | None,
    expected_code: int | str,
    expected_description: str,
) -> None:
    """Tests for meter location codes we have no fixture for."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == str(expected_state)

    mock_responses(
        aioclient_mock,
        fixture_set="symo",
        override_data={
            "symo/GetMeterRealtimeData.json": [
                (["Body", "Data", "0", "Meter_Location_Current"], location_code),
            ],
        },
    )
    await setup_fronius_integration(hass)
    assert_state("sensor.smart_meter_63a_meter_location", expected_code)
    assert_state(
        "sensor.smart_meter_63a_meter_location_description", expected_description
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
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
    await setup_fronius_integration(hass)

    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 59
    # states are rounded to 4 decimals
    assert_state("sensor.solarnet_energy_day", 10828)
    assert_state("sensor.solarnet_total_energy", 44186900)
    assert_state("sensor.solarnet_energy_year", 25507686)
    assert_state("sensor.solarnet_power_grid", 975.31)
    assert_state("sensor.solarnet_power_grid_import", 975.31)
    assert_state("sensor.solarnet_power_grid_export", 0)
    assert_state("sensor.solarnet_power_load", -975.31)
    assert_state("sensor.solarnet_power_load_consumed", 975.31)
    assert_state("sensor.solarnet_relative_autonomy", 0)

    # Second test at daytime when inverter is producing
    mock_responses(aioclient_mock, night=False)
    freezer.tick(FroniusPowerFlowUpdateCoordinator.default_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    # 54 because power_flow `rel_SelfConsumption` and `P_PV` is not `null` anymore
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 61
    assert_state("sensor.solarnet_energy_day", 1101.7001)
    assert_state("sensor.solarnet_total_energy", 44188000)
    assert_state("sensor.solarnet_energy_year", 25508788)
    assert_state("sensor.solarnet_power_grid", 1703.74)
    assert_state("sensor.solarnet_power_grid_import", 1703.74)
    assert_state("sensor.solarnet_power_grid_export", 0)
    assert_state("sensor.solarnet_power_load", -2814.74)
    assert_state("sensor.solarnet_power_load_generated", 0)
    assert_state("sensor.solarnet_power_load_consumed", 2814.74)
    assert_state("sensor.solarnet_power_photovoltaics", 1111)
    assert_state("sensor.solarnet_relative_autonomy", 39.4708)
    assert_state("sensor.solarnet_relative_self_consumption", 100)

    # Third test at nighttime - default values are used
    mock_responses(aioclient_mock, night=True)
    freezer.tick(FroniusPowerFlowUpdateCoordinator.default_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 61
    assert_state("sensor.solarnet_energy_day", 10828)
    assert_state("sensor.solarnet_total_energy", 44186900)
    assert_state("sensor.solarnet_energy_year", 25507686)
    assert_state("sensor.solarnet_power_grid", 975.31)
    assert_state("sensor.solarnet_power_load", -975.31)
    assert_state("sensor.solarnet_power_photovoltaics", 0)
    assert_state("sensor.solarnet_relative_autonomy", 0)
    assert_state("sensor.solarnet_relative_self_consumption", 0)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_gen24(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Fronius Gen24 inverter entities."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == str(expected_state)

    mock_responses(aioclient_mock, fixture_set="gen24")
    config_entry = await setup_fronius_integration(hass, is_logger=False)

    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 59
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    assert_state("sensor.inverter_name_total_energy", 1530193.42)
    # Gen24 devices may report 0 for total energy while doing firmware updates.
    # This should yield "unknown" state instead of 0.
    mock_responses(
        aioclient_mock,
        fixture_set="gen24",
        override_data={
            "gen24/GetInverterRealtimeData_Device_1.json": [
                (["Body", "Data", "TOTAL_ENERGY", "Value"], 0),
            ],
        },
    )
    freezer.tick(FroniusInverterUpdateCoordinator.default_interval)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert_state("sensor.inverter_name_total_energy", "unknown")


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_gen24_storage(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
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

    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 73
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    # Devices
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


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_primo_s0(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    device_registry: dr.DeviceRegistry,
    freezer: FrozenDateTimeFactory,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test Fronius Primo dual inverter with S0 meter entities."""

    def assert_state(entity_id, expected_state):
        state = hass.states.get(entity_id)
        assert state
        assert state.state == str(expected_state)

    mock_responses(aioclient_mock, fixture_set="primo_s0", inverter_ids=[1, 2])
    config_entry = await setup_fronius_integration(hass, is_logger=True)

    assert len(hass.states.async_all(domain_filter=SENSOR_DOMAIN)) == 49
    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)

    # Devices
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
