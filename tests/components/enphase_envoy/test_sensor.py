"""Test Enphase Envoy diagnostics."""
from unittest.mock import patch

from pyenphase import Envoy, EnvoyData
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.enphase_envoy import DOMAIN
from homeassistant.components.enphase_envoy.const import Platform
from homeassistant.components.enphase_envoy.coordinator import EnphaseUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry

# list of sensor,state to test for creation and correct value
TEST_ENTITIES = [
    ("sensor.envoy_1234_current_power_production", 1234 / 1000),
    ("sensor.envoy_1234_energy_production_today", 1234 / 1000),
    ("sensor.envoy_1234_energy_production_last_seven_days", 1234 / 1000),
    ("sensor.envoy_1234_lifetime_energy_production", 1234 / 1000000),
    ("sensor.envoy_1234_current_power_consumption", 1234 / 1000),
    ("sensor.envoy_1234_energy_consumption_today", 1234 / 1000),
    ("sensor.envoy_1234_energy_consumption_last_seven_days", 1234 / 1000),
    ("sensor.envoy_1234_lifetime_energy_consumption", 1234 / 1000000),
    ("sensor.envoy_1234_current_power_production_l1", 1234 / 1000),
    ("sensor.envoy_1234_energy_production_today_l1", 1233 / 1000),
    ("sensor.envoy_1234_energy_production_last_seven_days_l1", 1231 / 1000),
    ("sensor.envoy_1234_lifetime_energy_production_l1", 1232 / 1000000),
    ("sensor.envoy_1234_current_power_production_l2", 2234 / 1000),
    ("sensor.envoy_1234_energy_production_today_l2", 2233 / 1000),
    ("sensor.envoy_1234_energy_production_last_seven_days_l2", 2231 / 1000),
    ("sensor.envoy_1234_lifetime_energy_production_l2", 2232 / 1000000),
    ("sensor.envoy_1234_current_power_production_l3", 3234 / 1000),
    ("sensor.envoy_1234_energy_production_today_l3", 3233 / 1000),
    ("sensor.envoy_1234_energy_production_last_seven_days_l3", 3231 / 1000),
    ("sensor.envoy_1234_lifetime_energy_production_l3", 3232 / 1000000),
    ("sensor.envoy_1234_current_power_consumption_l1", 1324 / 1000),
    ("sensor.envoy_1234_energy_consumption_today_l1", 1323 / 1000),
    ("sensor.envoy_1234_energy_consumption_last_seven_days_l1", 1321 / 1000),
    ("sensor.envoy_1234_lifetime_energy_consumption_l1", 1322 / 1000000),
    ("sensor.envoy_1234_current_power_consumption_l2", 2324 / 1000),
    ("sensor.envoy_1234_energy_consumption_today_l2", 2323 / 1000),
    ("sensor.envoy_1234_energy_consumption_last_seven_days_l2", 2321 / 1000),
    ("sensor.envoy_1234_lifetime_energy_consumption_l2", 2322 / 1000000),
    ("sensor.envoy_1234_current_power_consumption_l3", 3324 / 1000),
    ("sensor.envoy_1234_energy_consumption_today_l3", 3323 / 1000),
    ("sensor.envoy_1234_energy_consumption_last_seven_days_l3", 3321 / 1000),
    ("sensor.envoy_1234_lifetime_energy_consumption_l3", 3322 / 1000000),
    ("sensor.inverter_1", 1),
    ("sensor.envoy_1234_current_net_power_consumption", 101 / 1000),
    ("sensor.envoy_1234_current_net_power_consumption_l1", 21 / 1000),
    ("sensor.envoy_1234_current_net_power_consumption_l2", 31 / 1000),
    ("sensor.envoy_1234_current_net_power_consumption_l3", 51 / 1000),
    ("sensor.envoy_1234_lifetime_net_energy_consumption", 21234 / 1000000),
    ("sensor.envoy_1234_lifetime_net_energy_consumption_l1", 212341 / 1000000),
    ("sensor.envoy_1234_lifetime_net_energy_consumption_l2", 212342 / 1000000),
    ("sensor.envoy_1234_lifetime_net_energy_consumption_l3", 212343 / 1000000),
    ("sensor.envoy_1234_lifetime_net_energy_production", 22345 / 1000000),
    ("sensor.envoy_1234_lifetime_net_energy_production_l1", 223451 / 1000000),
    ("sensor.envoy_1234_lifetime_net_energy_production_l2", 223452 / 1000000),
    ("sensor.envoy_1234_lifetime_net_energy_production_l3", 223453 / 1000000),
]

# list of sensor,state added as disabled, only test for existence
DISABLED_TEST_ENTITIES = [
    ("sensor.inverter_1_last_reported", 0),
    ("sensor.envoy_1234_frequency_net_consumption_ct", 0),
    ("sensor.envoy_1234_frequency_net_consumption_ct_l1", 0),
    ("sensor.envoy_1234_frequency_net_consumption_ct_l2", 0),
    ("sensor.envoy_1234_frequency_net_consumption_ct_l3", 0),
    ("sensor.envoy_1234_voltage_net_consumption_ct", 0),
    ("sensor.envoy_1234_voltage_net_consumption_ct_l1", 0),
    ("sensor.envoy_1234_voltage_net_consumption_ct_l2", 0),
    ("sensor.envoy_1234_voltage_net_consumption_ct_l3", 0),
    ("sensor.envoy_1234_metering_status_net_consumption_ct", 0),
    ("sensor.envoy_1234_metering_status_net_consumption_ct_l1", 0),
    ("sensor.envoy_1234_metering_status_net_consumption_ct_l2", 0),
    ("sensor.envoy_1234_metering_status_net_consumption_ct_l3", 0),
    ("sensor.envoy_1234_meter_status_flags_active_net_consumption_ct", 0),
    ("sensor.envoy_1234_meter_status_flags_active_net_consumption_ct_l1", 0),
    ("sensor.envoy_1234_meter_status_flags_active_net_consumption_ct_l2", 0),
    ("sensor.envoy_1234_meter_status_flags_active_net_consumption_ct_l3", 0),
    ("sensor.envoy_1234_metering_status_production_ct", 0),
    ("sensor.envoy_1234_metering_status_production_ct_l1", 0),
    ("sensor.envoy_1234_metering_status_production_ct_l2", 0),
    ("sensor.envoy_1234_metering_status_production_ct_l3", 0),
    ("sensor.envoy_1234_meter_status_flags_active_production_ct", 0),
    ("sensor.envoy_1234_meter_status_flags_active_production_ct_l1", 0),
    ("sensor.envoy_1234_meter_status_flags_active_production_ct_l2", 0),
    ("sensor.envoy_1234_meter_status_flags_active_production_ct_l3", 0),
]


@pytest.fixture(name="setup_enphase_envoy_sensor")
async def setup_enphase_envoy_sensor_fixture(hass, config, mock_envoy):
    """Define a fixture to set up Enphase Envoy with sensor platform only."""
    with patch(
        "homeassistant.components.enphase_envoy.config_flow.Envoy",
        return_value=mock_envoy,
    ), patch(
        "homeassistant.components.enphase_envoy.Envoy",
        return_value=mock_envoy,
    ), patch(
        "homeassistant.components.enphase_envoy.PLATFORMS",
        [Platform.SENSOR],
    ):
        assert await async_setup_component(hass, DOMAIN, config)
        await hass.async_block_till_done()
        yield


async def test_sensor(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    setup_enphase_envoy_sensor,
) -> None:
    """Test Enphase_Envoy SENSOR entities."""
    coordinator: EnphaseUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    envoy: Envoy = coordinator.envoy
    assert envoy

    envoy_data: EnvoyData | None = envoy.data
    assert envoy_data

    entity_registry = er.async_get(hass)
    assert entity_registry

    # compare registered entities against snapshot of prior run
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, config_entry.entry_id
    )
    assert entity_entries, f"No entries for config entry {config_entry.entry_id}"
    assert entity_entries == snapshot

    # Test if all entities still have same state
    for entity_entry in entity_entries:
        assert hass.states.get(entity_entry.entity_id) == snapshot(
            name=f"{entity_entry.entity_id}-state"
        )

    # test if expected entities are registered and have expected values
    for key, value in TEST_ENTITIES:
        assert entity_registry.async_is_registered(
            key
        ), f"{key} not registered as entity"
        assert (state := hass.states.get(key)), f"{key} has no state"
        assert (key_value := dict(state.as_dict())["state"]) == str(
            value
        ), f"{key}: {key_value} <> {value}"

    # test if disabled by default entities are registered
    for key, value in DISABLED_TEST_ENTITIES:
        assert entity_registry.async_is_registered(
            key
        ), f"{key} {value} not registered as entity"
        assert hass.states.get(key) is None, f"{key} has unexpected state"

    # test if any new entities are available and not yet in [DISABLED_]TEST_ENTITIES lists
    test_entities = dict(TEST_ENTITIES)
    disabled_test_entities = dict(DISABLED_TEST_ENTITIES)
    for entity_entry in entity_entries:
        assert (
            entity_entry.entity_id in test_entities
            or entity_entry.entity_id in disabled_test_entities
        ), f"{entity_entry.entity_id} not found in TEST_ENTITIES nor DISABLED_TEST_ENTITIES"
