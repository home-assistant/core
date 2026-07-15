"""Tests for the GridX sensor platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.gridx.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_LIVE_DATA, PASSWORD, USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, mock_gridx_connector: MagicMock
) -> MockConfigEntry:
    """Load the GridX integration with mocked connector."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        title=USERNAME,
        unique_id=USERNAME.lower(),
    )
    entry.add_to_hass(hass)

    mock_gridx_connector.retrieve_live_data.return_value = [MOCK_LIVE_DATA]

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_sensor_unique_ids(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """All sensor entities must have a unique_id."""
    entry = setup_integration
    entity_registry = er.async_get(hass)
    entities = [
        e
        for e in entity_registry.entities.values()
        if e.config_entry_id == entry.entry_id
    ]
    assert len(entities) > 0
    unique_ids = [e.unique_id for e in entities]
    assert len(unique_ids) == len(set(unique_ids)), "Duplicate unique_ids found"


async def test_live_sensor_values(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Test that live sensor values match the mock data."""
    entry = setup_integration
    # Entity names depend on translation; check via unique_id pattern
    registry = er.async_get(hass)
    entity = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.unique_id}_photovoltaic"
    )
    assert entity is not None
    state = hass.states.get(entity)
    assert state is not None
    assert state.state == "1512"


async def test_battery_sensor_present(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Battery sensors should be available when battery data is present."""
    entry = setup_integration
    registry = er.async_get(hass)
    entity = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.unique_id}_battery_stateOfCharge"
    )
    assert entity is not None
    state = hass.states.get(entity)
    assert state is not None
    # 0.77 * 100 = 77.0
    assert float(state.state) == pytest.approx(77.0)


async def test_battery_sensors_not_created_without_battery(
    hass: HomeAssistant, mock_gridx_connector: MagicMock
) -> None:
    """Battery sensors are not created when no battery data is present."""
    live_no_battery = {k: v for k, v in MOCK_LIVE_DATA.items() if k != "battery"}
    mock_gridx_connector.retrieve_live_data.return_value = [live_no_battery]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "other@example.com",
            CONF_PASSWORD: PASSWORD,
        },
        title="other@example.com",
        unique_id="other@example.com",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.unique_id}_battery_stateOfCharge"
    )
    assert entity is None


async def test_optional_subsystem_sensors_created_when_present(
    hass: HomeAssistant, mock_gridx_connector: MagicMock
) -> None:
    """EV, heat pump and heater sensors are created when their data exists."""
    live_full = {
        **MOCK_LIVE_DATA,
        "evChargingStation": {"power": 11000, "stateOfCharge": 0.42},
        "heatPumps": [{"power": 1500}],
        "heaters": [{"power": 2000, "temperature": 48.5}],
    }
    mock_gridx_connector.retrieve_live_data.return_value = [live_full]

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "full@example.com",
            CONF_PASSWORD: PASSWORD,
        },
        title="full@example.com",
        unique_id="full@example.com",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    for key in ("ev_power", "heatpump_power", "heater_temperature"):
        assert (
            registry.async_get_entity_id("sensor", DOMAIN, f"{entry.unique_id}_{key}")
            is not None
        )


async def test_grid_meter_ws_to_wh_conversion(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """GridMeterReadingPositive is in Ws and must be divided by 3600 to get Wh."""
    entry = setup_integration
    registry = er.async_get(hass)
    entity = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.unique_id}_gridMeterReadingPositive"
    )
    assert entity is not None
    state = hass.states.get(entity)
    assert state is not None
    # 7393320000 Ws / 3600 = 2053700.0 Wh
    assert float(state.state) == pytest.approx(2053700.0, rel=1e-4)


async def test_live_sensor_value_fn_type_error(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Live sensor returns STATE_UNKNOWN when value_fn raises TypeError on bad data."""
    entry = setup_integration
    # gridMeterReadingPositive divides by 3600; "not-a-number" / 3600 raises TypeError
    bad_data = {**MOCK_LIVE_DATA, "gridMeterReadingPositive": "not-a-number"}
    entry.runtime_data.coordinator.async_set_updated_data(bad_data)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.unique_id}_gridMeterReadingPositive"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_sensor_value_fn_value_error(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Sensor returns STATE_UNKNOWN when value_fn raises ValueError."""
    entry = setup_integration
    # selfConsumptionRate uses float(...); float("invalid") raises ValueError
    bad_data = {**MOCK_LIVE_DATA, "selfConsumptionRate": "invalid"}
    entry.runtime_data.coordinator.async_set_updated_data(bad_data)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.unique_id}_selfConsumptionRate"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN
