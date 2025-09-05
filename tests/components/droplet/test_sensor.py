"""Test Droplet sensors."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from homeassistant.components.sensor import (
    ATTR_STATE_CLASS,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import ATTR_DEVICE_CLASS
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_sensors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_droplet_discovery: AsyncMock,
    mock_droplet_connection: AsyncMock,
    mock_droplet: AsyncMock,
) -> None:
    """Test Droplet sensors."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.mock_title_signal_quality").state == "strong_signal"
    assert hass.states.get("sensor.mock_title_server_status").state == "connected"
    assert hass.states.get("sensor.mock_title_flow_rate").state == "0.0264172052358148"
    assert hass.states.get("sensor.mock_title_water").state == "0.264172052358148"

    assert (
        hass.states.get("sensor.mock_title_signal_quality").attributes[
            ATTR_DEVICE_CLASS
        ]
        == SensorDeviceClass.ENUM
    )
    assert (
        hass.states.get("sensor.mock_title_server_status").attributes[ATTR_DEVICE_CLASS]
        == SensorDeviceClass.ENUM
    )
    assert (
        hass.states.get("sensor.mock_title_flow_rate").attributes[ATTR_DEVICE_CLASS]
        == SensorDeviceClass.VOLUME_FLOW_RATE
    )
    assert (
        hass.states.get("sensor.mock_title_water").attributes[ATTR_DEVICE_CLASS]
        == SensorDeviceClass.WATER
    )
    assert (
        hass.states.get("sensor.mock_title_flow_rate").attributes[ATTR_STATE_CLASS]
        == SensorStateClass.MEASUREMENT
    )
    assert (
        hass.states.get("sensor.mock_title_water").attributes[ATTR_STATE_CLASS]
        == SensorStateClass.TOTAL
    )


async def mock_listen_forever(_, callback) -> None:
    """Mock Droplet API's listen forever."""
    callback(None)


async def test_sensors_update_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_droplet_discovery: AsyncMock,
    mock_droplet_connection: AsyncMock,
    mock_droplet: AsyncMock,
) -> None:
    """Test Droplet async update data."""
    attrs = {
        "get_flow_rate.return_value": 0.5,
        "get_volume_delta.return_value": 1.0,
        "get_volume_last_fetched.return_value": datetime(
            2025, 1, 1, 0, 0, 0, tzinfo=UTC
        ),
        "get_signal_quality.return_value": "no_signal",
        "get_server_status.return_value": "disconnected",
        "listen_forever.side_effect": mock_listen_forever,
    }
    mock_droplet.configure_mock(**attrs)

    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("sensor.mock_title_signal_quality").state == "no_signal"
    assert hass.states.get("sensor.mock_title_server_status").state == "disconnected"
    assert hass.states.get("sensor.mock_title_flow_rate").state == "0.132086026179074"
    assert hass.states.get("sensor.mock_title_water").state == "0.000264172052358148"
    assert (
        hass.states.get("sensor.mock_title_water").attributes.get("last_reset")
        == "2025-01-01T00:00:00+00:00"
    )
