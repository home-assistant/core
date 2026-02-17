"""Test the sensors provided by the Powerfox integration."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, snapshot_platform
from tests.components.conftest import AsyncMock


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_sensors(
    hass: HomeAssistant,
    mock_iometer_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Iometer sensors."""
    with patch("homeassistant.components.iometer.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_values_from_reading(
    hass: HomeAssistant,
    mock_iometer_client,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that sensor values are correctly extracted from reading data."""
    with patch("homeassistant.components.iometer.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    # Verify initial values from fixture
    assert (
        hass.states.get("sensor.iometer_1isk0000000000_meter_number").state
        == "1ISK0000000000"
    )
    assert (
        hass.states.get("sensor.iometer_1isk0000000000_total_consumption").state
        == "1234.5"
    )
    assert (
        hass.states.get("sensor.iometer_1isk0000000000_consumption_tariff_t1").state
        == "1904.5"
    )
    assert (
        hass.states.get("sensor.iometer_1isk0000000000_consumption_tariff_t2").state
        == "9876.21"
    )
    assert (
        hass.states.get("sensor.iometer_1isk0000000000_total_production").state
        == "5432.1"
    )
    assert hass.states.get("sensor.iometer_1isk0000000000_power").state == "100"


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_sensor_attributes(
    hass: HomeAssistant,
    mock_iometer_client,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that sensor attributes are set correctly."""
    with patch("homeassistant.components.iometer.PLATFORMS", [Platform.SENSOR]):
        await setup_integration(hass, mock_config_entry)

    # Test power sensor attributes
    state = hass.states.get("sensor.iometer_1isk0000000000_power")
    assert state is not None
    assert state.attributes["device_class"] == "power"
    assert state.attributes["unit_of_measurement"] == "W"

    # Test energy sensor attributes
    state = hass.states.get("sensor.iometer_1isk0000000000_total_consumption")
    assert state is not None
    assert state.attributes["device_class"] == "energy"
    assert state.attributes["unit_of_measurement"] == "Wh"

    # Test battery sensor attributes
    state = hass.states.get("sensor.iometer_1isk0000000000_battery_level")
    assert state is not None
    assert state.attributes["device_class"] == "battery"
    assert state.attributes["unit_of_measurement"] == "%"
