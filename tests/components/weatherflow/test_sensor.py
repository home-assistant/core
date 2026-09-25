"""Tests for the WeatherFlow sensor platform."""

from unittest.mock import patch

import pytest
from pyweatherflowudp.aioudp import LocalEndpoint
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.unit_system import (
    METRIC_SYSTEM,
    US_CUSTOMARY_SYSTEM,
    UnitSystem,
)

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform

RAIN_LAST_MINUTE = "sensor.st_00000001_precipitation"
STATION_PRESSURE = "sensor.st_00000001_air_pressure"
VAPOR_PRESSURE = "sensor.st_00000001_vapor_pressure"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_config_entry: MockConfigEntry,
    mock_udp_endpoint: LocalEndpoint,
) -> None:
    """Test all sensor entities."""
    with patch("homeassistant.components.weatherflow.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry, mock_udp_endpoint)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("unit_system", "entity_id", "unit"),
    [
        pytest.param(METRIC_SYSTEM, STATION_PRESSURE, "hPa", id="metric-pressure"),
        pytest.param(METRIC_SYSTEM, VAPOR_PRESSURE, "hPa", id="metric-vapor"),
        pytest.param(METRIC_SYSTEM, RAIN_LAST_MINUTE, "mm", id="metric-rain"),
        pytest.param(US_CUSTOMARY_SYSTEM, STATION_PRESSURE, "inHg", id="us-pressure"),
        pytest.param(US_CUSTOMARY_SYSTEM, VAPOR_PRESSURE, "inHg", id="us-vapor"),
        pytest.param(US_CUSTOMARY_SYSTEM, RAIN_LAST_MINUTE, "in", id="us-rain"),
    ],
)
async def test_unit_system(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_udp_endpoint: LocalEndpoint,
    unit_system: UnitSystem,
    entity_id: str,
    unit: str,
) -> None:
    """Test sensors are shown in the units of the configured unit system."""
    hass.config.units = unit_system
    await setup_integration(hass, mock_config_entry, mock_udp_endpoint)

    assert hass.states.get(entity_id).attributes[ATTR_UNIT_OF_MEASUREMENT] == unit
