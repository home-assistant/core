"""Tests for the air-Q sensor platform."""

from unittest.mock import AsyncMock

from homeassistant.components.airq.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform
from .common import TEST_DEVICE_DATA, TEST_DEVICE_INFO


async def test_sensor_state_updates_on_coordinator_refresh(
    hass: HomeAssistant,
    mock_airq: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that sensor state reflects coordinator.data after a refresh."""
    await setup_platform(hass, Platform.SENSOR)

    entity_id = entity_registry.async_get_entity_id(
        Platform.SENSOR, DOMAIN, f"{TEST_DEVICE_INFO['id']}_co2"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == TEST_DEVICE_DATA["co2"]

    new_co2 = TEST_DEVICE_DATA["co2"] + 1
    mock_airq.get_latest_data.return_value = {"co2": new_co2, "Status": "OK"}
    coordinator = hass.config_entries.async_entries(DOMAIN)[0].runtime_data
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == new_co2
