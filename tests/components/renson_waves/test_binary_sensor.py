"""Tests for Renson WAVES binary sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.renson_waves.binary_sensor import async_setup_entry
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_binary_sensor_setup_entry(
    hass: HomeAssistant,
    mock_coordinator,
):
    """Test binary sensor setup entry creates entities."""
    entry = ConfigEntry(
        domain="renson_waves",
        title="WAVES",
        data={CONF_HOST: "192.168.1.100", CONF_PORT: 8000},
        version=1,
    )
    entry.runtime_data = mock_coordinator

    mock_add_entities = AsyncMock()

    await async_setup_entry(hass, entry, mock_add_entities)

    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args[0][0]

    # Should have 4 binary sensors
    assert len(entities) == 4


@pytest.mark.asyncio
async def test_binary_sensor_values(
    hass: HomeAssistant,
    mock_coordinator,
):
    """Test binary sensor is_on values."""
    entry = ConfigEntry(
        domain="renson_waves",
        title="WAVES",
        data={CONF_HOST: "192.168.1.100", CONF_PORT: 8000},
        version=1,
    )
    entry.runtime_data = mock_coordinator

    mock_add_entities = AsyncMock()

    await async_setup_entry(hass, entry, mock_add_entities)

    entities = mock_add_entities.call_args[0][0]

    # Check WiFi connected sensor
    wifi_sensor = next(
        (e for e in entities if e.entity_description.key == "wifi_connected"), None
    )
    if wifi_sensor:
        assert wifi_sensor.is_on is True

    # Check boost enabled sensor (should be False with our mock data)
    boost_sensor = next(
        (e for e in entities if e.entity_description.key == "room_boost_enabled"),
        None,
    )
    if boost_sensor:
        assert boost_sensor.is_on is False
