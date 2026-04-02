"""Tests for the Duco sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from duco.exceptions import DucoConnectionError
import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.usefixtures("init_integration")
async def test_sensor_entity_state(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that the sensor entity is created with the correct state."""
    entity_id = "sensor.living_ventilation_state"

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "AUTO"

    entry = entity_registry.async_get(entity_id)
    assert entry is not None
    assert entry.unique_id == "aa:bb:cc:dd:ee:ff_1_ventilation_state"


@pytest.mark.usefixtures("init_integration")
async def test_coordinator_update_marks_unavailable(
    hass: HomeAssistant,
    mock_duco_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that entities become unavailable when the coordinator fails."""
    mock_duco_client.async_get_nodes = AsyncMock(
        side_effect=DucoConnectionError("offline")
    )

    await mock_config_entry.runtime_data.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get("sensor.living_ventilation_state")
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
