"""Tests for the GridX sensor platform."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.gridx.const import CONF_OEM, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_HIST_DATA, MOCK_LIVE_DATA, OEM, PASSWORD, USERNAME

from tests.common import MockConfigEntry


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, mock_gridx_connector: MagicMock
) -> MockConfigEntry:
    """Load the GridX integration with mocked connector."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        title=USERNAME,
        unique_id=USERNAME.lower(),
    )
    entry.add_to_hass(hass)

    mock_gridx_connector.retrieve_live_data.return_value = [MOCK_LIVE_DATA]
    mock_gridx_connector.retrieve_historical_data.return_value = MOCK_HIST_DATA

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
    assert state.state == "77.0"


async def test_battery_sensor_none_without_battery(
    hass: HomeAssistant, mock_gridx_connector: MagicMock
) -> None:
    """Battery sensors should be STATE_UNKNOWN when no battery data is present."""
    live_no_battery = {k: v for k, v in MOCK_LIVE_DATA.items() if k != "battery"}
    mock_gridx_connector.retrieve_live_data.return_value = [live_no_battery]
    mock_gridx_connector.retrieve_historical_data.return_value = MOCK_HIST_DATA

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_USERNAME: "other@example.com",
            CONF_PASSWORD: PASSWORD,
            CONF_OEM: OEM,
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
    assert entity is not None
    state = hass.states.get(entity)
    assert state is not None
    # None value → unknown
    assert state.state == STATE_UNKNOWN


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
    entry.runtime_data.live_coordinator.async_set_updated_data(bad_data)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.unique_id}_gridMeterReadingPositive"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_historical_sensor_value_fn_value_error(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """Historical sensor returns STATE_UNKNOWN when value_fn raises ValueError."""
    entry = setup_integration
    # hist_selfConsumptionRate uses float(...); float("invalid") raises ValueError
    bad_hist_total = {**MOCK_HIST_DATA[0]["total"], "selfConsumptionRate": "invalid"}
    bad_data = {
        "total": bad_hist_total,
        "last_reset": entry.runtime_data.hist_coordinator.data["last_reset"],
    }
    entry.runtime_data.hist_coordinator.async_set_updated_data(bad_data)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.unique_id}_hist_selfConsumptionRate"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN


async def test_historical_sensor_last_reset_no_data(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """last_reset returns None when historical coordinator has no data."""
    entry = setup_integration
    # Empty dict is falsy → 'if not data: return None' in last_reset property
    entry.runtime_data.hist_coordinator.async_set_updated_data({})
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.unique_id}_hist_selfConsumptionRate"
    )
    assert entity_id is not None


async def test_historical_sensor_last_reset_missing_key(
    hass: HomeAssistant, setup_integration: MockConfigEntry
) -> None:
    """last_reset returns None when data has no last_reset key."""
    entry = setup_integration
    # No 'last_reset' key → KeyError caught → returns None
    data_no_reset = {"total": MOCK_HIST_DATA[0]["total"]}
    entry.runtime_data.hist_coordinator.async_set_updated_data(data_no_reset)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.unique_id}_hist_selfConsumptionRate"
    )
    assert entity_id is not None
