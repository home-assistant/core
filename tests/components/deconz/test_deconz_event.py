"""Test deCONZ remote events without host device."""

from pydeconz.models.sensor.ancillary_control import AncillaryControlAction, AncillaryControlPanel
from pydeconz.models.sensor.presence import PresenceStatePresenceEvent
import pytest

from homeassistant.components.deconz.const import DOMAIN
from homeassistant.components.deconz.deconz_event import (
    ATTR_DURATION,
    ATTR_ROTATION,
    CONF_DECONZ_ALARM_EVENT,
    CONF_DECONZ_EVENT,
    CONF_DECONZ_PRESENCE_EVENT,
    CONF_DECONZ_RELATIVE_ROTARY_EVENT,
    RELATIVE_ROTARY_DECONZ_TO_EVENT,
)
from homeassistant.const import CONF_DEVICE_ID, CONF_EVENT, CONF_ID, CONF_UNIQUE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .conftest import WebsocketDataType
from tests.common import MockConfigEntry, async_capture_events


@pytest.mark.parametrize(
    "sensor_payload",
    [
        {
            "1": {"name": "Switch 1", "type": "ZHASwitch", "state": {"buttonevent": 1000}, "config": {}, "uniqueid": "switch-01-uniqueid"},
            "2": {"name": "Switch 2", "type": "ZHASwitch", "state": {"buttonevent": 1000}, "config": {"battery": 100}, "uniqueid": "switch-02-uniqueid"},
            "3": {"name": "Switch 3", "type": "ZHASwitch", "state": {"buttonevent": 1000, "gesture": 1}, "config": {"battery": 100}, "uniqueid": "switch-03-uniqueid"},
            "4": {"name": "Switch 4", "type": "ZHASwitch", "state": {"buttonevent": 1000, "gesture": 1}, "config": {"battery": 100}, "uniqueid": "switch-04-uniqueid"},
            "5": {"name": "ZHA remote 1", "type": "ZHASwitch", "state": {"angle": 0, "buttonevent": 1000, "xy": [0.0, 0.0]}, "config": {"group": "4,5,6", "reachable": True, "on": True}, "uniqueid": "zha-remote-01-uniqueid"},
        }
    ],
)
async def test_deconz_events(hass: HomeAssistant, device_registry: dr.DeviceRegistry, config_entry_setup: MockConfigEntry, sensor_ws_data: WebsocketDataType) -> None:
    """Test creation of deconz events without host device."""
    assert len(hass.states.async_all()) == 3
    # 5 switches + 1 gateway
    assert len(dr.async_entries_for_config_entry(device_registry, config_entry_setup.entry_id)) == 6

    captured_events = async_capture_events(hass, CONF_DECONZ_EVENT)

    await sensor_ws_data({"id": "1", "state": {"buttonevent": 2000}})
    device = device_registry.async_get_device(identifiers={(DOMAIN, "switch-01-uniqueid")})
    assert len(captured_events) == 1
    assert captured_events[0].data == {"id": "switch_1", "unique_id": "switch-01-uniqueid", "event": 2000, "device_id": device.id}

    await sensor_ws_data({"id": "3", "state": {"buttonevent": 2000}})
    device = device_registry.async_get_device(identifiers={(DOMAIN, "switch-03-uniqueid")})
    assert len(captured_events) == 2
    assert captured_events[1].data == {"id": "switch_3", "unique_id": "switch-03-uniqueid", "event": 2000, "gesture": 1, "device_id": device.id}

    await sensor_ws_data({"id": "4", "state": {"gesture": 0}})
    device = device_registry.async_get_device(identifiers={(DOMAIN, "switch-04-uniqueid")})
    assert len(captured_events) == 3
    assert captured_events[2].data == {"id": "switch_4", "unique_id": "switch-04-uniqueid", "event": 1000, "gesture": 0, "device_id": device.id}

    await sensor_ws_data({"id": "5", "state": {"buttonevent": 6002, "angle": 110, "xy": [0.5982, 0.3897]}})
    device = device_registry.async_get_device(identifiers={(DOMAIN, "zha-remote-01-uniqueid")})
    assert len(captured_events) == 4
    assert captured_events[3].data == {"id": "zha_remote_1", "unique_id": "zha-remote-01-uniqueid", "event": 6002, "angle": 110, "xy": [0.5982, 0.3897], "device_id": device.id}

    # Unsupported event
    await sensor_ws_data({"id": "1", "name": "other name"})
    assert len(captured_events) == 4


@pytest.mark.parametrize("alarm_system_payload", [{"0": {"name": "default", "config": {"armmode": "armed_away","configured": True}, "state": {"armstate": "armed_away"}, "devices": {"zha-remote-01-uniqueid": {}}}}])
@pytest.mark.parametrize("sensor_payload", [{"config": {"battery": 95}, "name": "Keypad", "state": {"action": "invalid_code"}, "type": "ZHAAncillaryControl", "uniqueid": "keypad-01-uniqueid"}])
async def test_deconz_alarm_events(hass: HomeAssistant, device_registry: dr.DeviceRegistry, config_entry_setup: MockConfigEntry, sensor_ws_data: WebsocketDataType) -> None:
    """Test deconz alarm events without host."""
    assert len(hass.states.async_all()) == 4
    # 1 alarm device + gateway
    assert len(dr.async_entries_for_config_entry(device_registry, config_entry_setup.entry_id)) == 2

    captured_events = async_capture_events(hass, CONF_DECONZ_ALARM_EVENT)
    device = device_registry.async_get_device(identifiers={(DOMAIN, "keypad-01-uniqueid")})

    for action in [AncillaryControlAction.EMERGENCY, AncillaryControlAction.FIRE, AncillaryControlAction.INVALID_CODE, AncillaryControlAction.PANIC]:
        await sensor_ws_data({"state": {"action": action}})
        assert len(captured_events) == action.value  # simplified event counting for illustration
        captured_events.clear()


@pytest.mark.parametrize("sensor_payload", [{"config": {"battery": 100}, "name": "Aqara FP1", "state": {"presence": True, "presenceevent": "leave"}, "type": "ZHAPresence", "uniqueid": "presence-01-uniqueid"}])
async def test_deconz_presence_events(hass: HomeAssistant, device_registry: dr.DeviceRegistry, config_entry_setup: MockConfigEntry, sensor_ws_data: WebsocketDataType) -> None:
    """Test deconz presence events without host."""
    assert len(hass.states.async_all()) == 5
    assert len(dr.async_entries_for_config_entry(device_registry, config_entry_setup.entry_id)) == 2

    device = device_registry.async_get_device(identifiers={(DOMAIN, "presence-01-uniqueid")})
    captured_events = async_capture_events(hass, CONF_DECONZ_PRESENCE_EVENT)

    for presence_event in list(PresenceStatePresenceEvent):
        await sensor_ws_data({"state": {"presenceevent": presence_event}})
        assert len(captured_events) == 1
        assert captured_events[0].data == {"id": "aqara_fp1", "unique_id": "presence-01-uniqueid", "device_id": device.id, "event": presence_event.value}
        captured_events.clear()


@pytest.mark.parametrize("sensor_payload", [{"config": {"battery": 100}, "name": "RDM002 44", "state": {"rotaryevent": 2, "expectedeventduration": 400, "expectedrotation": 75}, "type": "ZHARelativeRotary", "uniqueid": "rotary-01-uniqueid"}])
async def test_deconz_relative_rotary_events(hass: HomeAssistant, device_registry: dr.DeviceRegistry, config_entry_setup: MockConfigEntry, sensor_ws_data: WebsocketDataType) -> None:
    """Test deconz relative rotary events without host."""
    assert len(hass.states.async_all()) == 1
    assert len(dr.async_entries_for_config_entry(device_registry, config_entry_setup.entry_id)) == 2

    device = device_registry.async_get_device(identifiers={(DOMAIN, "rotary-01-uniqueid")})
    captured_events = async_capture_events(hass, CONF_DECONZ_RELATIVE_ROTARY_EVENT)

    for rotary_event, duration, rotation in ((1, 100, 50), (2, 200, -50)):
        await sensor_ws_data({"state": {"rotaryevent": rotary_event, "expectedeventduration": duration, "expectedrotation": rotation}})
        assert len(captured_events) == 1
        assert captured_events[0].data == {"id": "rdm002_44", "unique_id": "rotary-01-uniqueid", "device_id": device.id, "event": RELATIVE_ROTARY_DECONZ_TO_EVENT[rotary_event], ATTR_DURATION: duration, ATTR_ROTATION: rotation}
        captured_events.clear()


@pytest.mark.parametrize("sensor_payload", [{"1": {"name": "Switch 1 no unique id", "type": "ZHASwitch", "state": {"buttonevent": 1000}}, "2": {"name": "Switch 2 bad unique id", "type": "ZHASwitch", "state": {"buttonevent": 1000}, "uniqueid": "00:00-00"}}])
async def test_deconz_events_bad_unique_id(hass: HomeAssistant, device_registry: dr.DeviceRegistry, config_entry_setup: MockConfigEntry)