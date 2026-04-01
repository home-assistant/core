"""Tests for the GridX sensor platform."""

from unittest.mock import MagicMock, patch

import pytest

from homeassistant.components.gridx.const import CONF_OEM, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

from .conftest import MOCK_HIST_DATA, MOCK_LIVE_DATA, OEM, PASSWORD, USERNAME


@pytest.fixture
async def setup_integration(hass: HomeAssistant, mock_gridx_connector: MagicMock):
    """Load the GridX integration with mocked connector."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        title=USERNAME,
    )
    entry.add_to_hass(hass)

    mock_gridx_connector.retrieve_live_data.return_value = [MOCK_LIVE_DATA]
    mock_gridx_connector.retrieve_historical_data.return_value = MOCK_HIST_DATA

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_sensor_unique_ids(hass: HomeAssistant, setup_integration) -> None:
    """All sensor entities must have a unique_id."""
    from homeassistant.helpers import entity_registry as er

    entry = setup_integration
    entity_registry = er.async_get(hass)
    entities = [
        e for e in entity_registry.entities.values() if e.config_entry_id == entry.entry_id
    ]
    assert len(entities) > 0
    unique_ids = [e.unique_id for e in entities]
    assert len(unique_ids) == len(set(unique_ids)), "Duplicate unique_ids found"


async def test_live_sensor_values(hass: HomeAssistant, setup_integration) -> None:
    """Test that live sensor values match the mock data."""
    entry = setup_integration
    state = hass.states.get(f"sensor.gridx_gridbox_pv_power")
    # Entity names depend on translation; check via unique_id pattern
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    entity = registry.async_get_entity_id("sensor", DOMAIN, f"{entry.entry_id}_photovoltaic")
    assert entity is not None
    state = hass.states.get(entity)
    assert state is not None
    assert state.state == "1512"


async def test_battery_sensor_present(hass: HomeAssistant, setup_integration) -> None:
    """Battery sensors should be available when battery data is present."""
    entry = setup_integration
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    entity = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_battery_stateOfCharge"
    )
    assert entity is not None
    state = hass.states.get(entity)
    assert state is not None
    # 0.77 * 100 = 77.0
    assert state.state == "77.0"


async def test_battery_sensor_none_without_battery(
    hass: HomeAssistant, mock_gridx_connector: MagicMock
) -> None:
    """Battery sensors should return None (unavailable) when no battery data."""
    live_no_battery = {k: v for k, v in MOCK_LIVE_DATA.items() if k != "battery"}
    mock_gridx_connector.retrieve_live_data.return_value = [live_no_battery]
    mock_gridx_connector.retrieve_historical_data.return_value = MOCK_HIST_DATA

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "other@example.com", CONF_PASSWORD: PASSWORD, CONF_OEM: OEM},
        title="other@example.com",
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    entity = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_battery_stateOfCharge"
    )
    assert entity is not None
    state = hass.states.get(entity)
    # None value → unknown
    assert state.state == STATE_UNKNOWN


async def test_grid_meter_ws_to_wh_conversion(
    hass: HomeAssistant, setup_integration
) -> None:
    """gridMeterReadingPositive is in Ws — must be divided by 3600 to get Wh."""
    entry = setup_integration
    from homeassistant.helpers import entity_registry as er

    registry = er.async_get(hass)
    entity = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{entry.entry_id}_gridMeterReadingPositive"
    )
    assert entity is not None
    state = hass.states.get(entity)
    assert state is not None
    # 7393320000 Ws / 3600 = 2053700.0 Wh
    assert float(state.state) == pytest.approx(2053700.0, rel=1e-4)
