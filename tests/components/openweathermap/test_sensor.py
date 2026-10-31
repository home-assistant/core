"""Tests for OpenWeatherMap sensors."""

import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.openweathermap.const import (
    OWM_MODE_AIRPOLLUTION,
    OWM_MODE_FREE_CURRENT,
    OWM_MODE_FREE_FORECAST,
    OWM_MODE_V30,
    OWM_MODE_V40,
)
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_platform


@pytest.mark.parametrize(
    "mode",
    [OWM_MODE_V30, OWM_MODE_V40, OWM_MODE_FREE_CURRENT, OWM_MODE_AIRPOLLUTION],
    indirect=True,
)
@pytest.mark.usefixtures("owm_client_mock")
async def test_sensor_states(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor states are collected from library correctly."""

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize("mode", [OWM_MODE_FREE_FORECAST], indirect=True)
@pytest.mark.usefixtures("owm_client_mock")
async def test_mode_no_sensor(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test modes that do not provide any sensor."""

    await setup_platform(hass, mock_config_entry, [Platform.SENSOR])
    assert len(entity_registry.entities) == 0
