"""Test SensorPush Cloud sensors."""

from __future__ import annotations

from copy import deepcopy
from unittest.mock import AsyncMock

import pytest

from homeassistant.components.sensorpush_cloud.const import MAX_TIME_BETWEEN_UPDATES
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import MOCK_DATA, MOCK_ENTITY_IDS

from tests.common import MockConfigEntry


@pytest.mark.data(MOCK_DATA)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_create_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_helper: AsyncMock,
) -> None:
    """Test we can create sensors."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for entity_id in MOCK_ENTITY_IDS:
        entity = hass.states.get(entity_id)
        assert entity
        assert entity.state != STATE_UNAVAILABLE


@pytest.mark.data(MOCK_DATA)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_unavailable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_helper: AsyncMock,
) -> None:
    """Test we can set sensors to unavailable."""
    data = deepcopy(MOCK_DATA)
    for datum in data.values():
        datum.last_update = dt_util.utcnow() - MAX_TIME_BETWEEN_UPDATES
    mock_helper.async_get_data.return_value = data

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    for entity_id in MOCK_ENTITY_IDS:
        entity = hass.states.get(entity_id)
        assert entity
        assert entity.state == STATE_UNAVAILABLE
