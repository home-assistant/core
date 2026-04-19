"""Tests for the WattWächter Plus sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.components.wattwaechter.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import MOCK_DEVICE_ID, MOCK_METER_DATA_MINIMAL

from tests.common import MockConfigEntry


def _get_entity_id(entity_registry: er.EntityRegistry, obis_code: str) -> str | None:
    """Get entity ID from the registry by OBIS code unique_id."""
    return entity_registry.async_get_entity_id(
        "sensor", DOMAIN, f"{MOCK_DEVICE_ID}_{obis_code}"
    )


async def test_known_obis_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that known OBIS codes create sensors with correct attributes."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Energy sensor (1.8.0 - total consumption)
    entity_id = _get_entity_id(entity_registry, "1.8.0")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 12345.678
    assert state.attributes["unit_of_measurement"] == "kWh"
    assert state.attributes["device_class"] == SensorDeviceClass.ENERGY
    assert state.attributes["state_class"] == SensorStateClass.TOTAL_INCREASING

    # Power sensor (16.7.0 - active power)
    entity_id = _get_entity_id(entity_registry, "16.7.0")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 1500.5
    assert state.attributes["unit_of_measurement"] == "W"
    assert state.attributes["device_class"] == SensorDeviceClass.POWER

    # Voltage sensor (32.7.0)
    entity_id = _get_entity_id(entity_registry, "32.7.0")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 230.1
    assert state.attributes["device_class"] == SensorDeviceClass.VOLTAGE

    # Current sensor (31.7.0)
    entity_id = _get_entity_id(entity_registry, "31.7.0")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 6.52
    assert state.attributes["device_class"] == SensorDeviceClass.CURRENT

    # Frequency sensor (14.7.0)
    entity_id = _get_entity_id(entity_registry, "14.7.0")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert float(state.state) == 50.01
    assert state.attributes["device_class"] == SensorDeviceClass.FREQUENCY


async def test_minimal_meter_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that only reported OBIS codes create sensors (dynamic)."""
    mock_client.meter_data.return_value = MOCK_METER_DATA_MINIMAL

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Sensors for reported OBIS codes should exist
    assert _get_entity_id(entity_registry, "1.8.0") is not None
    assert _get_entity_id(entity_registry, "16.7.0") is not None

    # Sensors for unreported OBIS codes should NOT exist
    assert _get_entity_id(entity_registry, "2.8.0") is None
    assert _get_entity_id(entity_registry, "32.7.0") is None
    assert _get_entity_id(entity_registry, "31.7.0") is None
