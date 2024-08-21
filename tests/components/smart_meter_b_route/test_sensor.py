"""Tests for the Smart Meter B-Route sensor."""

from unittest.mock import Mock

import pytest

from homeassistant.components.smart_meter_b_route.coordinator import (
    BRouteUpdateCoordinator,
)
from homeassistant.components.smart_meter_b_route.sensor import (
    SENSOR_DESCRIPTIONS,
    async_setup_entry,
)
from homeassistant.core import HomeAssistant

from . import configure_integration


async def test_async_setup_entry(hass: HomeAssistant, mock_momonga) -> None:
    """Test async_setup_entry function."""
    config_entry = configure_integration(hass)
    mock_async_add_entity = Mock()

    def mock_async_add_entities(entities: list):
        for entity in entities:
            mock_async_add_entity(entity)

    await async_setup_entry(hass, config_entry, mock_async_add_entities)

    assert len(mock_async_add_entity.mock_calls) is len(SENSOR_DESCRIPTIONS)


@pytest.mark.parametrize(
    ("index", "entity_id"),
    [
        (0, "sensor.smart_meter_b_route_b_route_id_instantaneous_current_r_phase"),
        (1, "sensor.smart_meter_b_route_b_route_id_instantaneous_current_t_phase"),
        (2, "sensor.smart_meter_b_route_b_route_id_instantaneous_power"),
        (3, "sensor.smart_meter_b_route_b_route_id_total_consumption"),
    ],
)
async def test_smart_meter_b_route_sensor_update(
    hass: HomeAssistant, index: int, entity_id: str, mock_momonga
) -> None:
    """Test SmartMeterBRouteSensor update."""
    config_entry = configure_integration(hass)
    coordinator: BRouteUpdateCoordinator = config_entry.runtime_data
    await hass.config_entries.async_setup(config_entry.entry_id)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    entity = hass.states.get(entity_id)
    assert entity.state == index + 1
    mock_momonga.assert_called()


async def test_smart_meter_b_route_sensor_no_update(
    hass: HomeAssistant, mock_momonga
) -> None:
    """Test SmartMeterBRouteSensor with no update."""
    entity_id = "sensor.smart_meter_b_route_b_route_id_total_consumption"
    config_entry = configure_integration(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    coordinator: BRouteUpdateCoordinator = config_entry.runtime_data
    coordinator.data = {}
    await hass.async_block_till_done()

    entity = hass.states.get(entity_id)
    assert entity.state is None
    mock_momonga.assert_not_called()
