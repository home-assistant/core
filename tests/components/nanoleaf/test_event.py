"""Tests for the Nanoleaf event platform."""

from unittest.mock import AsyncMock

from aionanoleaf2 import TouchEvent
import pytest

from homeassistant.components.nanoleaf.const import DOMAIN, NANOLEAF_EVENT
from homeassistant.const import CONF_DEVICE_ID, CONF_TYPE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import device_registry as dr

from . import setup_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("gesture_id", "gesture", "panel_id"),
    [
        pytest.param(0, "single_tap", 7, id="single_tap"),
        pytest.param(1, "double_tap", 7, id="double_tap"),
        pytest.param(2, "swipe_up", -1, id="swipe_up"),
        pytest.param(3, "swipe_down", -1, id="swipe_down"),
        pytest.param(4, "swipe_left", -1, id="swipe_left"),
        pytest.param(5, "swipe_right", -1, id="swipe_right"),
    ],
)
async def test_touch_events(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    caplog: pytest.LogCaptureFixture,
    gesture_id: int,
    gesture: str,
    panel_id: int,
) -> None:
    """Test documented gestures update the entity and preserve the bus event format."""
    mock_nanoleaf.model = "NL42"
    await setup_integration(hass, mock_config_entry)

    events: list[Event] = []
    hass.bus.async_listen(NANOLEAF_EVENT, events.append)
    touch_callback = mock_nanoleaf.listen_events.call_args.kwargs["touch_callback"]
    await touch_callback(TouchEvent({"gesture": gesture_id, "panelId": panel_id}))
    await hass.async_block_till_done()

    state = hass.states.get("event.nanoleaf_touch_gesture")
    assert state is not None
    assert state.state != STATE_UNKNOWN
    assert state.attributes["event_type"] == gesture
    assert "Received unknown touch gesture" not in caplog.text

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, mock_nanoleaf.serial_no), mock_config_entry.entry_id
    )
    assert device is not None
    assert len(events) == 1
    assert events[0].data == {CONF_DEVICE_ID: device.id, CONF_TYPE: gesture}


async def test_unknown_touch_event(
    hass: HomeAssistant,
    mock_nanoleaf: AsyncMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test an undocumented gesture is ignored and still logged."""
    mock_nanoleaf.model = "NL42"
    await setup_integration(hass, mock_config_entry)

    events: list[Event] = []
    hass.bus.async_listen(NANOLEAF_EVENT, events.append)
    touch_callback = mock_nanoleaf.listen_events.call_args.kwargs["touch_callback"]
    await touch_callback(TouchEvent({"gesture": 6, "panelId": 7}))
    await hass.async_block_till_done()

    state = hass.states.get("event.nanoleaf_touch_gesture")
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert not events
    assert "Received unknown touch gesture ID 6" in caplog.text
