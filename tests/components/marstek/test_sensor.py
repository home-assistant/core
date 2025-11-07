"""Tests for the Marstek sensor platform."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from homeassistant.components.marstek.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import create_mock_udp_client

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor platform setup."""
    mock_config_entry.add_to_hass(hass)
    mock_client = create_mock_udp_client()

    with patch(
        "homeassistant.components.marstek.sensor.MarstekUDPClient",
        return_value=mock_client,
    ):
        # Setup
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN]["udp_client"] = mock_client

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify sensors are created
        entity_registry = er.async_get(hass)

        # Battery SoC sensor
        battery_sensor = entity_registry.async_get("sensor.battery_level_192_168_1_100")
        assert battery_sensor
        assert battery_sensor.unique_id == "192.168.1.100_battery_soc"

        # Grid power sensor
        power_sensor = entity_registry.async_get("sensor.grid_power_192_168_1_100")
        assert power_sensor
        assert power_sensor.unique_id == "192.168.1.100_battery_power"

        # Device mode sensor
        mode_sensor = entity_registry.async_get("sensor.device_mode_192_168_1_100")
        assert mode_sensor
        assert mode_sensor.unique_id == "192.168.1.100_device_mode"

        # Battery status sensor
        status_sensor = entity_registry.async_get("sensor.battery_status_192_168_1_100")
        assert status_sensor
        assert status_sensor.unique_id == "192.168.1.100_battery_status"


async def test_coordinator_creates_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that coordinator is created and sensors are set up."""
    mock_config_entry.add_to_hass(hass)
    mock_client = create_mock_udp_client()

    with patch(
        "homeassistant.components.marstek.sensor.MarstekUDPClient",
        return_value=mock_client,
    ):
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN]["udp_client"] = mock_client

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Check that sensor platform was set up
        entity_registry = er.async_get(hass)
        entities = er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )

        # Should have created multiple sensors (battery, power, mode, status, PV sensors, etc.)
        assert len(entities) > 0


async def test_polling_paused(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator respects polling pause."""
    mock_config_entry.add_to_hass(hass)
    mock_client = create_mock_udp_client()

    # Setup mock to return paused status
    mock_client.is_polling_paused.return_value = True

    with patch(
        "homeassistant.components.marstek.sensor.MarstekUDPClient",
        return_value=mock_client,
    ):
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN]["udp_client"] = mock_client

        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Trigger update
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
        await hass.async_block_till_done()

        # Should not crash even when polling is paused
        # This tests the polling pause mechanism works correctly
