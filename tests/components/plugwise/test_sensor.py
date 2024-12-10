"""Tests for the Plugwise Sensor integration."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.plugwise.const import DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity
import homeassistant.helpers.entity_registry as er

from tests.common import MockConfigEntry


async def test_adam_climate_sensor_entities(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of climate related sensor entities."""
    state = hass.states.get("sensor.adam_outdoor_temperature")
    assert state
    assert float(state.state) == 7.81

    state = hass.states.get("sensor.cv_pomp_electricity_consumed")
    assert state
    assert float(state.state) == 35.6

    state = hass.states.get("sensor.onoff_water_temperature")
    assert state
    assert float(state.state) == 70.0

    state = hass.states.get("sensor.cv_pomp_electricity_consumed_interval")
    assert state
    assert float(state.state) == 7.37

    await async_update_entity(hass, "sensor.zone_lisa_wk_battery")

    state = hass.states.get("sensor.zone_lisa_wk_battery")
    assert state
    assert int(state.state) == 34


async def test_adam_climate_sensor_entity_2(
    hass: HomeAssistant, mock_smile_adam_4: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of climate related sensor entities."""
    state = hass.states.get("sensor.woonkamer_humidity")
    assert state
    assert float(state.state) == 56.2


async def test_unique_id_migration_humidity(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_smile_adam_4: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test unique ID migration of -relative_humidity to -humidity."""
    mock_config_entry.add_to_hass(hass)

    # Entry to migrate
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "f61f1a2535f54f52ad006a3d18e459ca-relative_humidity",
        config_entry=mock_config_entry,
        suggested_object_id="woonkamer_humidity",
        disabled_by=None,
    )
    # Entry not needing migration
    entity_registry.async_get_or_create(
        SENSOR_DOMAIN,
        DOMAIN,
        "f61f1a2535f54f52ad006a3d18e459ca-battery",
        config_entry=mock_config_entry,
        suggested_object_id="woonkamer_battery",
        disabled_by=None,
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.woonkamer_humidity") is not None
    assert hass.states.get("sensor.woonkamer_battery") is not None

    entity_entry = entity_registry.async_get("sensor.woonkamer_humidity")
    assert entity_entry
    assert entity_entry.unique_id == "f61f1a2535f54f52ad006a3d18e459ca-humidity"

    entity_entry = entity_registry.async_get("sensor.woonkamer_battery")
    assert entity_entry
    assert entity_entry.unique_id == "f61f1a2535f54f52ad006a3d18e459ca-battery"


async def test_anna_as_smt_climate_sensor_entities(
    hass: HomeAssistant, mock_smile_anna: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of climate related sensor entities."""
    state = hass.states.get("sensor.opentherm_outdoor_air_temperature")
    assert state
    assert float(state.state) == 3.0

    state = hass.states.get("sensor.opentherm_water_temperature")
    assert state
    assert float(state.state) == 29.1

    state = hass.states.get("sensor.opentherm_dhw_temperature")
    assert state
    assert float(state.state) == 46.3

    state = hass.states.get("sensor.anna_illuminance")
    assert state
    assert float(state.state) == 86.0


async def test_p1_dsmr_sensor_entities(
    hass: HomeAssistant, mock_smile_p1: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of power related sensor entities."""
    state = hass.states.get("sensor.p1_net_electricity_point")
    assert state
    assert int(state.state) == 486

    state = hass.states.get("sensor.p1_electricity_consumed_off_peak_cumulative")
    assert state
    assert float(state.state) == 17643.423

    state = hass.states.get("sensor.p1_electricity_produced_peak_point")
    assert state
    assert int(state.state) == 0

    state = hass.states.get("sensor.p1_electricity_consumed_peak_cumulative")
    assert state
    assert float(state.state) == 13966.608

    state = hass.states.get("sensor.p1_gas_consumed_cumulative")
    assert not state


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_p1_3ph_dsmr_sensor_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_smile_p1_2: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test creation of power related sensor entities."""
    state = hass.states.get("sensor.p1_electricity_phase_one_consumed")
    assert state
    assert int(state.state) == 1763

    state = hass.states.get("sensor.p1_electricity_phase_two_consumed")
    assert state
    assert int(state.state) == 1703

    state = hass.states.get("sensor.p1_electricity_phase_three_consumed")
    assert state
    assert int(state.state) == 2080

    # Default disabled sensor test
    state = hass.states.get("sensor.p1_voltage_phase_one")
    assert state
    assert float(state.state) == 233.2


async def test_p1_3ph_dsmr_sensor_disabled_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_smile_p1_2: MagicMock,
    init_integration: MockConfigEntry,
) -> None:
    """Test disabled power related sensor entities intent."""
    state = hass.states.get("sensor.p1_voltage_phase_one")
    assert not state


async def test_stretch_sensor_entities(
    hass: HomeAssistant, mock_stretch: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test creation of power related sensor entities."""
    state = hass.states.get("sensor.koelkast_92c4a_electricity_consumed")
    assert state
    assert float(state.state) == 50.5

    state = hass.states.get("sensor.droger_52559_electricity_consumed_interval")
    assert state
    assert float(state.state) == 0.0
