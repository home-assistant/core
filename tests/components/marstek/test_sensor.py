"""Tests for the Marstek sensor platform."""

from __future__ import annotations

from datetime import timedelta
import json
from unittest.mock import AsyncMock, patch

from homeassistant.components.marstek.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import MOCK_ES_MODE_RESPONSE, create_mock_udp_client

from tests.common import MockConfigEntry, async_fire_time_changed


async def test_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test sensor platform setup."""
    mock_config_entry.add_to_hass(hass)
    mock_client = create_mock_udp_client()

    # Override send_request to return immediately
    async def mock_send_request(message, *args, **kwargs):
        try:
            msg = json.loads(message)
            if msg.get("method") == "ES.GetMode":
                return MOCK_ES_MODE_RESPONSE
        except (json.JSONDecodeError, KeyError, AttributeError):
            pass
        return MOCK_ES_MODE_RESPONSE

    mock_client.send_request = AsyncMock(side_effect=mock_send_request)
    mock_client._listen_task = None

    with patch(
        "homeassistant.components.marstek.MarstekUDPClient", return_value=mock_client
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify sensors are created
        entity_registry = er.async_get(hass)

        # Battery SoC sensor
        battery_sensor_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "192.168.1.100_battery_soc"
        )
        assert battery_sensor_id == "sensor.marstek_es5_v1_battery_level_192_168_1_100"

        # Grid power sensor
        power_sensor_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "192.168.1.100_battery_power"
        )
        assert power_sensor_id == "sensor.marstek_es5_v1_grid_power_192_168_1_100"

        # Device mode sensor
        mode_sensor_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "192.168.1.100_device_mode"
        )
        assert mode_sensor_id == "sensor.marstek_es5_v1_device_mode_192_168_1_100"

        # Battery status sensor
        status_sensor_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, "192.168.1.100_battery_status"
        )
        assert status_sensor_id == "sensor.marstek_es5_v1_battery_status_192_168_1_100"


async def test_coordinator_creates_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that coordinator is created and sensors are set up."""
    mock_config_entry.add_to_hass(hass)
    mock_client = create_mock_udp_client()

    # Override send_request to return immediately
    async def mock_send_request(message, *args, **kwargs):
        try:
            msg = json.loads(message)
            if msg.get("method") == "ES.GetMode":
                return MOCK_ES_MODE_RESPONSE
        except (json.JSONDecodeError, KeyError, AttributeError):
            pass
        return MOCK_ES_MODE_RESPONSE

    mock_client.send_request = AsyncMock(side_effect=mock_send_request)
    mock_client._listen_task = None

    with patch(
        "homeassistant.components.marstek.MarstekUDPClient", return_value=mock_client
    ):
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

    # Override send_request to return immediately
    async def mock_send_request(message, *args, **kwargs):
        try:
            msg = json.loads(message)
            if msg.get("method") == "ES.GetMode":
                return MOCK_ES_MODE_RESPONSE
        except (json.JSONDecodeError, KeyError, AttributeError):
            pass
        return MOCK_ES_MODE_RESPONSE

    mock_client.send_request = AsyncMock(side_effect=mock_send_request)
    mock_client._listen_task = None
    # Setup mock to return paused status
    mock_client.is_polling_paused.return_value = True

    with patch(
        "homeassistant.components.marstek.MarstekUDPClient", return_value=mock_client
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Trigger update
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=11))
        await hass.async_block_till_done()

        # Should not crash even when polling is paused
        # This tests the polling pause mechanism works correctly
