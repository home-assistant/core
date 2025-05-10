"""Tests for OpenWeatherMap sensors."""

from unittest.mock import MagicMock

import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.openweathermap.const import (
    OWM_MODE_AIRPOLLUTION,
    OWM_MODE_FREE_CURRENT,
    OWM_MODE_FREE_FORECAST,
    OWM_MODE_V30,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize(
    "mode", [OWM_MODE_V30, OWM_MODE_FREE_CURRENT, OWM_MODE_AIRPOLLUTION], indirect=True
)
async def test_sensor_states(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    owm_client_mock: MagicMock,
    mode: str,
) -> None:
    """Test sensor states are correctly collected from library with different modes and mocked function responses."""

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("mode", [OWM_MODE_FREE_FORECAST], indirect=True)
async def test_mode_no_sensor(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    owm_client_mock: MagicMock,
    mode: str,
) -> None:
    """Test modes that do not provide any sensor."""

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    assert len(entity_registry.entities) == 0
