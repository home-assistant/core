"""Tests for the WLED switch platform."""
import json
from unittest.mock import MagicMock

import pytest
from wled import Device as WLEDDevice, WLEDConnectionError, WLEDError

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.wled.const import (
    ATTR_DURATION,
    ATTR_FADE,
    ATTR_TARGET_BRIGHTNESS,
    ATTR_UDP_PORT,
    SCAN_INTERVAL,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_ICON,
    ENTITY_CATEGORY_CONFIG,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import homeassistant.util.dt as dt_util

from tests.common import MockConfigEntry, async_fire_time_changed, load_fixture


async def test_switch_state(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Test the creation and values of the WLED switches."""
    entity_registry = er.async_get(hass)

    state = hass.states.get("switch.wled_rgb_light_nightlight")
    assert state
    assert state.attributes.get(ATTR_DURATION) == 60
    assert state.attributes.get(ATTR_ICON) == "mdi:weather-night"
    assert state.attributes.get(ATTR_TARGET_BRIGHTNESS) == 0
    assert state.attributes.get(ATTR_FADE)
    assert state.state == STATE_OFF

    entry = entity_registry.async_get("switch.wled_rgb_light_nightlight")
    assert entry
    assert entry.unique_id == "aabbccddeeff_nightlight"
    assert entry.entity_category == ENTITY_CATEGORY_CONFIG

    state = hass.states.get("switch.wled_rgb_light_sync_send")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:upload-network-outline"
    assert state.attributes.get(ATTR_UDP_PORT) == 21324
    assert state.state == STATE_OFF

    entry = entity_registry.async_get("switch.wled_rgb_light_sync_send")
    assert entry
    assert entry.unique_id == "aabbccddeeff_sync_send"
    assert entry.entity_category == ENTITY_CATEGORY_CONFIG

    state = hass.states.get("switch.wled_rgb_light_sync_receive")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:download-network-outline"
    assert state.attributes.get(ATTR_UDP_PORT) == 21324
    assert state.state == STATE_ON

    entry = entity_registry.async_get("switch.wled_rgb_light_sync_receive")
    assert entry
    assert entry.unique_id == "aabbccddeeff_sync_receive"
    assert entry.entity_category == ENTITY_CATEGORY_CONFIG

    state = hass.states.get("switch.wled_rgb_light_reverse")
    assert state
    assert state.attributes.get(ATTR_ICON) == "mdi:swap-horizontal-bold"
    assert state.state == STATE_OFF

    entry = entity_registry.async_get("switch.wled_rgb_light_reverse")
    assert entry
    assert entry.unique_id == "aabbccddeeff_reverse_0"
    assert entry.entity_category == ENTITY_CATEGORY_CONFIG


async def test_switch_change_state(
    hass: HomeAssistant, init_integration: MockConfigEntry, mock_wled: MagicMock
) -> None:
    """Test the change of state of the WLED switches."""

    # Nightlight
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.wled_rgb_light_nightlight"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.nightlight.call_count == 1
    mock_wled.nightlight.assert_called_with(on=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.wled_rgb_light_nightlight"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.nightlight.call_count == 2
    mock_wled.nightlight.assert_called_with(on=False)

    # Sync send
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.wled_rgb_light_sync_send"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.sync.call_count == 1
    mock_wled.sync.assert_called_with(send=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.wled_rgb_light_sync_send"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.sync.call_count == 2
    mock_wled.sync.assert_called_with(send=False)

    # Sync receive
    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.wled_rgb_light_sync_receive"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.sync.call_count == 3
    mock_wled.sync.assert_called_with(receive=False)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.wled_rgb_light_sync_receive"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.sync.call_count == 4
    mock_wled.sync.assert_called_with(receive=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.wled_rgb_light_reverse"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(segment_id=0, reverse=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "switch.wled_rgb_light_reverse"},
        blocking=True,
    )
    await hass.async_block_till_done()
    assert mock_wled.segment.call_count == 2
    mock_wled.segment.assert_called_with(segment_id=0, reverse=False)


async def test_switch_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED switches."""
    mock_wled.nightlight.side_effect = WLEDError

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.wled_rgb_light_nightlight"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.wled_rgb_light_nightlight")
    assert state
    assert state.state == STATE_OFF
    assert "Invalid response from API" in caplog.text


async def test_switch_connection_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test error handling of the WLED switches."""
    mock_wled.nightlight.side_effect = WLEDConnectionError

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "switch.wled_rgb_light_nightlight"},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("switch.wled_rgb_light_nightlight")
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert "Error communicating with API" in caplog.text


@pytest.mark.parametrize("mock_wled", ["wled/rgb_single_segment.json"], indirect=True)
async def test_switch_dynamically_handle_segments(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_wled: MagicMock,
) -> None:
    """Test if a new/deleted segment is dynamically added/removed."""
    segment0 = hass.states.get("switch.wled_rgb_light_reverse")
    segment1 = hass.states.get("switch.wled_rgb_light_segment_1_reverse")
    assert segment0
    assert segment0.state == STATE_OFF
    assert not segment1

    # Test adding a segment dynamically...
    return_value = mock_wled.update.return_value
    mock_wled.update.return_value = WLEDDevice(
        json.loads(load_fixture("wled/rgb.json"))
    )

    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    segment0 = hass.states.get("switch.wled_rgb_light_reverse")
    segment1 = hass.states.get("switch.wled_rgb_light_segment_1_reverse")
    assert segment0
    assert segment0.state == STATE_OFF
    assert segment1
    assert segment1.state == STATE_ON

    # Test remove segment again...
    mock_wled.update.return_value = return_value
    async_fire_time_changed(hass, dt_util.utcnow() + SCAN_INTERVAL)
    await hass.async_block_till_done()

    segment0 = hass.states.get("switch.wled_rgb_light_reverse")
    segment1 = hass.states.get("switch.wled_rgb_light_segment_1_reverse")
    assert segment0
    assert segment0.state == STATE_OFF
    assert segment1
    assert segment1.state == STATE_UNAVAILABLE
