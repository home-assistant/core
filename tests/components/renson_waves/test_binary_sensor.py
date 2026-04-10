"""Tests for Renson WAVES binary sensor platform."""

from __future__ import annotations

from unittest.mock import Mock

import pytest

from homeassistant.components.renson_waves.binary_sensor import async_setup_entry
from homeassistant.components.renson_waves.coordinator import RensonWavesCoordinator
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.mark.asyncio
async def test_binary_sensor_setup_entry(
    hass: HomeAssistant,
    mock_coordinator: RensonWavesCoordinator,
) -> None:
    """Test binary sensor setup entry creates entities."""
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

    assert len(entities) == 4


@pytest.mark.asyncio
async def test_binary_sensor_values(
    hass: HomeAssistant,
    mock_coordinator: RensonWavesCoordinator,
) -> None:
    """Test binary sensor is_on values."""
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

    wifi_sensor = next(
        entity
        for entity in entities
        if entity.entity_description.key == "wifi_connected"
    )
    assert wifi_sensor.is_on is True

    boost_sensor = next(
        entity
        for entity in entities
        if entity.entity_description.key == "room_boost_enabled"
    )
    assert boost_sensor.is_on is False
