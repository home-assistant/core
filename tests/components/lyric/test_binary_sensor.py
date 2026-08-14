"""Tests for the Honeywell Lyric binary sensor platform."""

from unittest.mock import MagicMock, patch

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.lyric.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import L1_ID, WLD3_ID

from tests.common import MockConfigEntry


async def test_leak_detector_binary_sensors(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    mock_lyric: MagicMock,
) -> None:
    """Test WLD3 and L1 leak detector binary sensors."""
    with patch("homeassistant.components.lyric.PLATFORMS", [Platform.BINARY_SENSOR]):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    for device_id, expected_state, expected_model in (
        (WLD3_ID, STATE_OFF, "WLD3"),
        (L1_ID, STATE_ON, "L1_SmartWaterSensor_Retail"),
    ):
        entity_id = entity_registry.async_get_entity_id(
            Platform.BINARY_SENSOR, DOMAIN, f"{device_id}_water_leak"
        )
        assert entity_id is not None
        state = hass.states.get(entity_id)
        assert state is not None
        assert state.state == expected_state
        assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.MOISTURE

        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, device_id), mock_config_entry.entry_id
        )
        assert device is not None
        assert device.model == expected_model
        assert not device.connections

    mock_lyric.locations[0].attributes["devices"][1]["isDeviceOffline"] = True
    mock_config_entry.runtime_data.async_set_updated_data(mock_lyric)
    await hass.async_block_till_done()

    entity_id = entity_registry.async_get_entity_id(
        Platform.BINARY_SENSOR, DOMAIN, f"{WLD3_ID}_water_leak"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE
