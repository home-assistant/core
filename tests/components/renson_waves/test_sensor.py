"""Tests for Renson WAVES sensor platform."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from homeassistant.components.renson_waves.coordinator import RensonWavesCoordinator
from homeassistant.components.renson_waves.sensor import async_setup_entry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_sensor_setup_entry(
    hass: HomeAssistant,
    mock_coordinator: RensonWavesCoordinator,
) -> None:
    """Test sensor setup entry creates entities."""
    entry = MockConfigEntry(
        domain="renson_waves",
        title="WAVES",
        data={CONF_HOST: "192.168.1.100", CONF_PORT: 8000},
        version=1,
    )
    entry.runtime_data = mock_coordinator

    mock_add_entities = Mock()

    await async_setup_entry(hass, entry, mock_add_entities)

    mock_add_entities.assert_called_once()
    entities = mock_add_entities.call_args.args[0]

    assert len(entities) > 8


@pytest.mark.asyncio
async def test_sensor_values(
    hass: HomeAssistant,
    mock_coordinator: RensonWavesCoordinator,
) -> None:
    """Test sensor native values."""
    entry = MockConfigEntry(
        domain="renson_waves",
        title="WAVES",
        data={CONF_HOST: "192.168.1.100", CONF_PORT: 8000},
        version=1,
    )
    entry.runtime_data = mock_coordinator

    mock_add_entities = Mock()

    await async_setup_entry(hass, entry, mock_add_entities)

    entities = mock_add_entities.call_args.args[0]

    uptime_sensor = next(
        entity
        for entity in entities
        if entity.entity_description.key == "uptime_seconds"
    )
    assert uptime_sensor.native_value == 86400

    wifi_ssid_sensor = next(
        entity for entity in entities if entity.entity_description.key == "wifi_ssid"
    )
    assert wifi_ssid_sensor.native_value == "HomeNetwork"
