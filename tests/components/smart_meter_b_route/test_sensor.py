"""Tests for the Smart Meter B-Route sensor."""

from unittest.mock import AsyncMock, Mock

import pytest

from homeassistant.components.smart_meter_b_route.coordinator import (
    BRouteUpdateCoordinator,
)
from homeassistant.components.smart_meter_b_route.sensor import (
    SENSOR_DESCRIPTIONS,
    SmartMeterBRouteSensor,
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
    ("index"),
    [
        (0),
        (1),
        (2),
        (3),
    ],
)
async def test_smart_meter_b_route_sensor_update(
    hass: HomeAssistant, index: int, mock_momonga
) -> None:
    """Test SmartMeterBRouteSensor update."""
    config_entry = configure_integration(hass)
    coordinator: BRouteUpdateCoordinator = config_entry.runtime_data
    await coordinator.async_refresh()

    description = SENSOR_DESCRIPTIONS[index]
    sensor = SmartMeterBRouteSensor(coordinator, description)
    sensor.async_write_ha_state = AsyncMock()

    sensor._handle_coordinator_update()
    await hass.async_block_till_done()

    assert sensor.state == index + 1
    assert sensor.native_unit_of_measurement == description.native_unit_of_measurement
    assert sensor.device_class == description.device_class

    sensor.async_write_ha_state.assert_called()


async def test_smart_meter_b_route_sensor_no_update(
    hass: HomeAssistant, mock_momonga
) -> None:
    """Test SmartMeterBRouteSensor with no update."""
    config_entry = configure_integration(hass)
    coordinator = config_entry.runtime_data

    sensor = SmartMeterBRouteSensor(coordinator, SENSOR_DESCRIPTIONS[0])
    sensor.async_write_ha_state = AsyncMock()

    coordinator.data = {}
    sensor._handle_coordinator_update()
    await hass.async_block_till_done()

    assert sensor.state is None

    sensor.async_write_ha_state.assert_not_called()
