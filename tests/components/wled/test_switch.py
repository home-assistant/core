"""Tests for the WLED switch platform."""
import json
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from wled import Device as WLEDDevice, WLEDConnectionError, WLEDError

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.wled.const import SCAN_INTERVAL
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import async_fire_time_changed, load_fixture

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.parametrize(
    ("entity_id", "method", "called_with_on", "called_with_off"),
    [
        (
            "switch.wled_rgb_light_nightlight",
            "nightlight",
            {"on": True},
            {"on": False},
        ),
        (
            "switch.wled_rgb_light_reverse",
            "segment",
            {"segment_id": 0, "reverse": True},
            {"segment_id": 0, "reverse": False},
        ),
        (
            "switch.wled_rgb_light_sync_receive",
            "sync",
            {"receive": True},
            {"receive": False},
        ),
        (
            "switch.wled_rgb_light_sync_send",
            "sync",
            {"send": True},
            {"send": False},
        ),
    ],
)
async def test_switch_state(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_wled: MagicMock,
    entity_id: str,
    method: str,
    called_with_on: dict[str, bool | int],
    called_with_off: dict[str, bool | int],
) -> None:
    """Test the creation and values of the WLED switches."""
    assert (state := hass.states.get(entity_id))
    assert state == snapshot

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot

    # Test on/off services
    method_mock = getattr(mock_wled, method)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: state.entity_id},
        blocking=True,
    )

    assert method_mock.call_count == 1
    method_mock.assert_called_with(**called_with_on)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: state.entity_id},
        blocking=True,
    )

    assert method_mock.call_count == 2
    method_mock.assert_called_with(**called_with_off)

    # Test invalid response, not becoming unavailable
    method_mock.side_effect = WLEDError
    with pytest.raises(HomeAssistantError, match="Invalid response from WLED API"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: state.entity_id},
            blocking=True,
        )

    assert method_mock.call_count == 3
    assert (state := hass.states.get(state.entity_id))
    assert state.state != STATE_UNAVAILABLE

    # Test connection error, leading to becoming unavailable
    method_mock.side_effect = WLEDConnectionError
    with pytest.raises(HomeAssistantError, match="Error communicating with WLED API"):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: state.entity_id},
            blocking=True,
        )

    assert method_mock.call_count == 4
    assert (state := hass.states.get(state.entity_id))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("device_fixture", ["rgb_single_segment"])
async def test_switch_dynamically_handle_segments(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_wled: MagicMock,
) -> None:
    """Test if a new/deleted segment is dynamically added/removed."""

    assert (segment0 := hass.states.get("switch.wled_rgb_light_reverse"))
    assert segment0.state == STATE_OFF
    assert not hass.states.get("switch.wled_rgb_light_segment_1_reverse")

    # Test adding a segment dynamically...
    return_value = mock_wled.update.return_value
    mock_wled.update.return_value = WLEDDevice(
        json.loads(load_fixture("wled/rgb.json"))
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (segment0 := hass.states.get("switch.wled_rgb_light_reverse"))
    assert segment0.state == STATE_OFF
    assert (segment1 := hass.states.get("switch.wled_rgb_light_segment_1_reverse"))
    assert segment1.state == STATE_ON

    # Test remove segment again...
    mock_wled.update.return_value = return_value
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (segment0 := hass.states.get("switch.wled_rgb_light_reverse"))
    assert segment0.state == STATE_OFF
    assert (segment1 := hass.states.get("switch.wled_rgb_light_segment_1_reverse"))
    assert segment1.state == STATE_UNAVAILABLE
