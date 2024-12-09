"""Tests for the Smart Meter B-Route sensor."""

from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
from momonga import MomongaError
import pytest

from homeassistant.components.smart_meter_b_route.const import DEFAULT_SCAN_INTERVAL
from homeassistant.components.smart_meter_b_route.sensor import (
    SENSOR_DESCRIPTIONS,
    async_setup_entry,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant

from . import configure_integration

from tests.common import async_fire_time_changed


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
    hass: HomeAssistant,
    index: int,
    entity_id: str,
    mock_momonga,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test SmartMeterBRouteSensor update."""
    config_entry = configure_integration(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(entity_id)
    assert entity.state == str(index + 1)


async def test_smart_meter_b_route_sensor_no_update(
    hass: HomeAssistant,
    mock_momonga,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test SmartMeterBRouteSensor with no update."""

    entity_id = "sensor.smart_meter_b_route_b_route_id_instantaneous_current_r_phase"
    config_entry = configure_integration(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    mock_momonga.return_value.get_instantaneous_current.side_effect = MomongaError
    freezer.tick(DEFAULT_SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)

    entity = hass.states.get(entity_id)
    assert entity.state is STATE_UNAVAILABLE
