"""Tests for Renson WAVES sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.renson_waves.sensor import async_setup_entry
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant


@pytest.mark.asyncio
async def test_sensor_setup_entry(
    hass: HomeAssistant,
    mock_coordinator,
):
    """Test sensor setup entry creates entities."""
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

    # Should have at least fixed sensors + constellation sensors
    assert len(entities) > 8


@pytest.mark.asyncio
async def test_sensor_values(
    hass: HomeAssistant,
    mock_coordinator,
):
    """Test sensor native values."""
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

    # Check fixed sensors have expected values
    uptime_sensor = next(
        (e for e in entities if e.entity_description.key == "uptime_seconds"), None
    )
    if uptime_sensor:
        assert uptime_sensor.native_value == 86400

    wifi_ssid_sensor = next(
        (e for e in entities if e.entity_description.key == "wifi_ssid"), None
    )
    if wifi_ssid_sensor:
        assert wifi_ssid_sensor.native_value == "HomeNetwork"
