"""Fixtures for energy component tests."""

from unittest.mock import patch

import pytest

from homeassistant.components.energy import async_get_manager
from homeassistant.components.energy.data import EnergyManager
from homeassistant.components.recorder import Recorder
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component


@pytest.fixture
def mock_is_entity_recorded():
    """Mock recorder.is_entity_recorded."""
    mocks = {}

    with patch(
        "homeassistant.components.recorder.is_entity_recorded",
        side_effect=lambda hass, entity_id: mocks.get(entity_id, True),
    ):
        yield mocks


@pytest.fixture
def mock_get_metadata():
    """Mock recorder.statistics.get_metadata."""
    mocks = {}

    def _get_metadata(_hass, *, statistic_ids):
        result = {}
        for statistic_id in statistic_ids:
            if statistic_id in mocks:
                if mocks[statistic_id] is not None:
                    result[statistic_id] = mocks[statistic_id]
            else:
                result[statistic_id] = (1, {})
        return result

    with patch(
        "homeassistant.components.recorder.statistics.get_metadata",
        wraps=_get_metadata,
    ):
        yield mocks


@pytest.fixture
async def mock_energy_manager(
    recorder_mock: Recorder, hass: HomeAssistant
) -> EnergyManager:
    """Set up energy."""
    assert await async_setup_component(hass, "energy", {"energy": {}})
    manager = await async_get_manager(hass)
    manager.data = manager.default_preferences()
    return manager
