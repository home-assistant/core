"""Tests for the WLED number platform."""
import json
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from wled import Device as WLEDDevice, WLEDConnectionError, WLEDError

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.wled.const import SCAN_INTERVAL
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import async_fire_time_changed, load_fixture

pytestmark = pytest.mark.usefixtures("init_integration")


@pytest.mark.parametrize(
    ("entity_id", "value", "called_arg"),
    [
        ("number.wled_rgb_light_segment_1_speed", 42, "speed"),
        ("number.wled_rgb_light_segment_1_intensity", 42, "intensity"),
    ],
)
async def test_numbers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_wled: MagicMock,
    entity_id: str,
    value: int,
    called_arg: str,
) -> None:
    """Test the creation and values of the WLED numbers."""
    assert (state := hass.states.get(entity_id))
    assert state == snapshot

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot

    # Test a regular state change service call
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    assert mock_wled.segment.call_count == 1
    mock_wled.segment.assert_called_with(segment_id=1, **{called_arg: value})

    # Test with WLED error
    mock_wled.segment.side_effect = WLEDError
    with pytest.raises(HomeAssistantError, match="Invalid response from WLED API"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
            blocking=True,
        )
    assert mock_wled.segment.call_count == 2

    # Ensure the entity is still available
    assert (state := hass.states.get(entity_id))
    assert state.state != STATE_UNAVAILABLE

    # Test when a connection error occurs
    mock_wled.segment.side_effect = WLEDConnectionError
    with pytest.raises(HomeAssistantError, match="Error communicating with WLED API"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
            blocking=True,
        )
    assert mock_wled.segment.call_count == 3

    # Ensure the entity became unavailable after the connection error
    assert (state := hass.states.get(entity_id))
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.parametrize("device_fixture", ["rgb_single_segment"])
@pytest.mark.parametrize(
    ("entity_id_segment0", "state_segment0", "entity_id_segment1", "state_segment1"),
    [
        (
            "number.wled_rgb_light_speed",
            "32",
            "number.wled_rgb_light_segment_1_speed",
            "16",
        ),
        (
            "number.wled_rgb_light_intensity",
            "128",
            "number.wled_rgb_light_segment_1_intensity",
            "64",
        ),
    ],
)
async def test_speed_dynamically_handle_segments(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_wled: MagicMock,
    entity_id_segment0: str,
    entity_id_segment1: str,
    state_segment0: str,
    state_segment1: str,
) -> None:
    """Test if a new/deleted segment is dynamically added/removed."""
    assert (segment0 := hass.states.get(entity_id_segment0))
    assert segment0.state == state_segment0
    assert not hass.states.get(entity_id_segment1)

    # Test adding a segment dynamically...
    return_value = mock_wled.update.return_value
    mock_wled.update.return_value = WLEDDevice(
        json.loads(load_fixture("wled/rgb.json"))
    )

    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (segment0 := hass.states.get(entity_id_segment0))
    assert segment0.state == state_segment0
    assert (segment1 := hass.states.get(entity_id_segment1))
    assert segment1.state == state_segment1

    # Test remove segment again...
    mock_wled.update.return_value = return_value
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (segment0 := hass.states.get(entity_id_segment0))
    assert segment0.state == state_segment0
    assert (segment1 := hass.states.get(entity_id_segment1))
    assert segment1.state == STATE_UNAVAILABLE
