"""Tests for Karaca Connect status sensor values and availability."""

from datetime import timedelta
from unittest.mock import AsyncMock

from karaca_connect_client import KaracaConnectionError
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.karaca_connect.const import (
    DOMAIN,
    UPDATE_INTERVAL_SECONDS,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util.dt import utcnow


async def _setup_sensor(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> str:
    """Set up the sensor and return its registered entity ID."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, "device-123_status"
    )
    assert entity_id is not None
    return entity_id


async def test_status_sensor_reports_live_cloud_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_karaca_client: AsyncMock,
) -> None:
    """Expose the real-device mode label from the cloud response."""
    mock_karaca_client.get_detail.return_value = {
        "detail": {"mode": 6, "modeName": "waterboiled"},
        "meta": {"connected": True},
    }
    entity_id = await _setup_sensor(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.state == "waterboiled"


async def test_standby_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_karaca_client: AsyncMock,
) -> None:
    """Use the standby label for mode 1."""
    entity_id = await _setup_sensor(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.state == "standby"


async def test_device_disconnected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_karaca_client: AsyncMock,
) -> None:
    """Mark the sensor unavailable if the API reports disconnection."""
    mock_karaca_client.get_detail.return_value = {
        "detail": {"mode": 6, "modeName": "waterboiled"},
        "meta": {"connected": False},
    }
    entity_id = await _setup_sensor(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE


async def test_missing_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_karaca_client: AsyncMock,
) -> None:
    """Avoid inventing a status when the API has no mode label."""
    mock_karaca_client.get_detail.return_value = {
        "detail": {},
        "meta": {"connected": True},
    }
    entity_id = await _setup_sensor(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNKNOWN


async def test_poll_error_and_recovery(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_karaca_client: AsyncMock,
) -> None:
    """Mark the sensor unavailable on cloud error and restore it on recovery."""
    entity_id = await _setup_sensor(hass, mock_config_entry)

    assert (state := hass.states.get(entity_id))
    assert state.state == "standby"

    mock_karaca_client.get_detail.side_effect = KaracaConnectionError()
    next_poll = utcnow() + timedelta(seconds=UPDATE_INTERVAL_SECONDS + 1)
    async_fire_time_changed(hass, next_poll)
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE

    mock_karaca_client.get_detail.side_effect = None
    mock_karaca_client.get_detail.return_value = {
        "detail": {"mode": 6, "modeName": "waterboiled"},
        "meta": {"connected": True},
    }
    async_fire_time_changed(
        hass, next_poll + timedelta(seconds=UPDATE_INTERVAL_SECONDS + 1)
    )
    await hass.async_block_till_done()

    assert (state := hass.states.get(entity_id))
    assert state.state == "waterboiled"
