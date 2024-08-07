"""Test deCONZ remote events."""

from pydeconz.models.sensor.ancillary_control import (
    AncillaryControlAction,
    AncillaryControlPanel,
)
from pydeconz.models.sensor.presence import PresenceStatePresenceEvent
import pytest

from homeassistant.components.deconz.const import DOMAIN as DECONZ_DOMAIN
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
            "1": {
                "name": "Switch 1",
                "type": "ZHASwitch",
                "state": {"buttonevent": 1000},
                "config": {},
                "uniqueid": "00:00:00:00:00:00:00:01-00",
            },
            "2": {
                "name": "Switch 2",
                "type": "ZHASwitch",
                "state": {"buttonevent": 1000},
                "config": {"battery": 100},
                "uniqueid": "00:00:00:00:00:00:00:02-00",
            },
            "3": {
                "name": "Switch 3",
                "type": "ZHASwitch",
                "state": {"buttonevent": 1000, "gesture": 1},
                "config": {"battery": 100},
                "uniqueid": "00:00:00:00:00:00:00:03-00",
            },
            "4": {
                "name": "Switch 4",
                "type": "ZHASwitch",
                "state": {"buttonevent": 1000, "gesture": 1},
                "config": {"battery": 100},
                "uniqueid": "00:00:00:00:00:00:00:04-00",
            },
            "5": {
                "name": "ZHA remote 1",
                "type": "ZHASwitch",
                "state": {"angle": 0, "buttonevent": 1000, "xy": [0.0, 0.0]},
                "config": {"group": "4,5,6", "reachable": True, "on": True},
                "uniqueid": "00:00:00:00:00:00:00:05-00",
            },
        }
    ],
)
async def test_deconz_events(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry_setup: MockConfigEntry,
    sensor_ws_data: WebsocketDataType,
) -> None:
    """Test successful creation of deconz events."""
    assert len(hass.states.async_all()) == 3
    # 5 switches + 2 additional devices for deconz service and host
    assert (
        len(
            dr.async_entries_for_config_entry(
                device_registry, config_entry_setup.entry_id
            )
        )
        == 7
    )
    assert hass.states.get("sensor.switch_2_battery").state == "100"
    assert hass.states.get("sensor.switch_3_battery").state == "100"
    assert hass.states.get("sensor.switch_4_battery").state == "100"

    captured_events = async_capture_events(hass, CONF_DECONZ_EVENT)

    await sensor_ws_data({"id": "1", "state": {"buttonevent": 2000}})

    device = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, "00:00:00:00:00:00:00:01")}
    )

    assert len(captured_events) == 1
    assert captured_events[0].data == {
        "id": "switch_1",
        "unique_id": "00:00:00:00:00:00:00:01",
        "event": 2000,
        "device_id": device.id,
    }

    await sensor_ws_data({"id": "3", "state": {"buttonevent": 2000}})

    device = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, "00:00:00:00:00:00:00:03")}
    )

    assert len(captured_events) == 2
    assert captured_events[1].data == {
        "id": "switch_3",
        "unique_id": "00:00:00:00:00:00:00:03",
        "event": 2000,
        "gesture": 1,
        "device_id": device.id,
    }

    await sensor_ws_data({"id": "4", "state": {"gesture": 0}})

    device = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, "00:00:00:00:00:00:00:04")}
    )

    assert len(captured_events) == 3
    assert captured_events[2].data == {
        "id": "switch_4",
        "unique_id": "00:00:00:00:00:00:00:04",
        "event": 1000,
        "gesture": 0,
        "device_id": device.id,
    }

    event_changed_sensor = {
        "id": "5",
        "state": {"buttonevent": 6002, "angle": 110, "xy": [0.5982, 0.3897]},
    }
    await sensor_ws_data(event_changed_sensor)

    device = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, "00:00:00:00:00:00:00:05")}
    )

    assert len(captured_events) == 4
    assert captured_events[3].data == {
        "id": "zha_remote_1",
        "unique_id": "00:00:00:00:00:00:00:05",
        "event": 6002,
        "angle": 110,
        "xy": [0.5982, 0.3897],
        "device_id": device.id,
    }

    # Unsupported event

    await sensor_ws_data({"id": "1", "name": "other name"})
    assert len(captured_events) == 4


@pytest.mark.parametrize(
    "alarm_system_payload",
    [
        {
            "0": {
                "name": "default",
                "config": {
                    "armmode": "armed_away",
                    "configured": True,
                    "disarmed_entry_delay": 0,
                    "disarmed_exit_delay": 0,
                    "armed_away_entry_delay": 120,
                    "armed_away_exit_delay": 120,
                    "armed_away_trigger_duration": 120,
                    "armed_stay_entry_delay": 120,
                    "armed_stay_exit_delay": 120,
                    "armed_stay_trigger_duration": 120,
                    "armed_night_entry_delay": 120,
                    "armed_night_exit_delay": 120,
                    "armed_night_trigger_duration": 120,
                },
                "state": {"armstate": "armed_away", "seconds_remaining": 0},
                "devices": {
                    "00:00:00:00:00:00:00:01-00": {},
                    "00:15:8d:00:02:af:95:f9-01-0101": {
                        "armmask": "AN",
                        "trigger": "state/vibration",
                    },
                },
            }
        }
    ],
)
@pytest.mark.parametrize(
    "sensor_payload",
    [
        {
            "config": {
                "battery": 95,
                "enrolled": 1,
                "on": True,
                "pending": [],
                "reachable": True,
            },
            "ep": 1,
            "etag": "5aaa1c6bae8501f59929539c6e8f44d6",
            "lastseen": "2021-07-25T18:07Z",
            "manufacturername": "lk",
            "modelid": "ZB-KeypadGeneric-D0002",
            "name": "Keypad",
            "state": {
                "action": "invalid_code",
                "lastupdated": "2021-07-25T18:02:51.172",
                "lowbattery": False,
                "panel": "exit_delay",
                "seconds_remaining": 55,
                "tampered": False,
            },
            "swversion": "3.13",
            "type": "ZHAAncillaryControl",
            "uniqueid": "00:00:00:00:00:00:00:01-00",
        }
    ],
)
async def test_deconz_alarm_events(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry_setup: MockConfigEntry,
    sensor_ws_data: WebsocketDataType,
) -> None:
    """Test successful creation of deconz alarm events."""
    assert len(hass.states.async_all()) == 4
    # 1 alarm control device + 2 additional devices for deconz service and host
    assert (
        len(
            dr.async_entries_for_config_entry(
                device_registry, config_entry_setup.entry_id
            )
        )
        == 3
    )

    captured_events = async_capture_events(hass, CONF_DECONZ_ALARM_EVENT)

    # Emergency event

    await sensor_ws_data({"state": {"action": AncillaryControlAction.EMERGENCY}})

    device = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, "00:00:00:00:00:00:00:01")}
    )

    assert len(captured_events) == 1
    assert captured_events[0].data == {
        CONF_ID: "keypad",
        CONF_UNIQUE_ID: "00:00:00:00:00:00:00:01",
        CONF_DEVICE_ID: device.id,
        CONF_EVENT: AncillaryControlAction.EMERGENCY.value,
    }

    # Fire event

    await sensor_ws_data({"state": {"action": AncillaryControlAction.FIRE}})

    device = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, "00:00:00:00:00:00:00:01")}
    )

    assert len(captured_events) == 2
    assert captured_events[1].data == {
        CONF_ID: "keypad",
        CONF_UNIQUE_ID: "00:00:00:00:00:00:00:01",
        CONF_DEVICE_ID: device.id,
        CONF_EVENT: AncillaryControlAction.FIRE.value,
    }

    # Invalid code event

    await sensor_ws_data({"state": {"action": AncillaryControlAction.INVALID_CODE}})

    device = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, "00:00:00:00:00:00:00:01")}
    )

    assert len(captured_events) == 3
    assert captured_events[2].data == {
        CONF_ID: "keypad",
        CONF_UNIQUE_ID: "00:00:00:00:00:00:00:01",
        CONF_DEVICE_ID: device.id,
        CONF_EVENT: AncillaryControlAction.INVALID_CODE.value,
    }

    # Panic event

    await sensor_ws_data({"state": {"action": AncillaryControlAction.PANIC}})

    device = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, "00:00:00:00:00:00:00:01")}
    )

    assert len(captured_events) == 4
    assert captured_events[3].data == {
        CONF_ID: "keypad",
        CONF_UNIQUE_ID: "00:00:00:00:00:00:00:01",
        CONF_DEVICE_ID: device.id,
        CONF_EVENT: AncillaryControlAction.PANIC.value,
    }

    # Only care for changes to specific action events

    await sensor_ws_data({"state": {"action": AncillaryControlAction.ARMED_AWAY}})
    assert len(captured_events) == 4

    # Only care for action events

    await sensor_ws_data({"state": {"panel": AncillaryControlPanel.ARMED_AWAY}})
    assert len(captured_events) == 4


@pytest.mark.parametrize(
    "sensor_payload",
    [
        {
            "config": {
                "devicemode": "undirected",
                "on": True,
                "reachable": True,
                "sensitivity": 3,
                "triggerdistance": "medium",
            },
            "etag": "13ff209f9401b317987d42506dd4cd79",
            "lastannounced": None,
            "lastseen": "2022-06-28T23:13Z",
            "manufacturername": "aqara",
            "modelid": "lumi.motion.ac01",
            "name": "Aqara FP1",
            "state": {
                "lastupdated": "2022-06-28T23:13:38.577",
                "presence": True,
                "presenceevent": "leave",
            },
            "swversion": "20210121",
            "type": "ZHAPresence",
            "uniqueid": "xx:xx:xx:xx:xx:xx:xx:xx-01-0406",
        }
    ],
)
async def test_deconz_presence_events(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry_setup: MockConfigEntry,
    sensor_ws_data: WebsocketDataType,
) -> None:
    """Test successful creation of deconz presence events."""
    assert len(hass.states.async_all()) == 5
    assert (
        len(
            dr.async_entries_for_config_entry(
                device_registry, config_entry_setup.entry_id
            )
        )
        == 3
    )

    device = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, "xx:xx:xx:xx:xx:xx:xx:xx")}
    )

    captured_events = async_capture_events(hass, CONF_DECONZ_PRESENCE_EVENT)

    for presence_event in (
        PresenceStatePresenceEvent.ABSENTING,
        PresenceStatePresenceEvent.APPROACHING,
        PresenceStatePresenceEvent.ENTER,
        PresenceStatePresenceEvent.ENTER_LEFT,
        PresenceStatePresenceEvent.ENTER_RIGHT,
        PresenceStatePresenceEvent.LEAVE,
        PresenceStatePresenceEvent.LEFT_LEAVE,
        PresenceStatePresenceEvent.RIGHT_LEAVE,
    ):
        await sensor_ws_data({"state": {"presenceevent": presence_event}})

        assert len(captured_events) == 1
        assert captured_events[0].data == {
            CONF_ID: "aqara_fp1",
            CONF_UNIQUE_ID: "xx:xx:xx:xx:xx:xx:xx:xx",
            CONF_DEVICE_ID: device.id,
            CONF_EVENT: presence_event.value,
        }
        captured_events.clear()

    # Unsupported presence event

    await sensor_ws_data({"state": {"presenceevent": PresenceStatePresenceEvent.NINE}})
    assert len(captured_events) == 0


@pytest.mark.parametrize(
    "sensor_payload",
    [
        {
            "config": {
                "battery": 100,
                "on": True,
                "reachable": True,
            },
            "etag": "463728970bdb7d04048fc4373654f45a",
            "lastannounced": "2022-07-03T13:57:59Z",
            "lastseen": "2022-07-03T14:02Z",
            "manufacturername": "Signify Netherlands B.V.",
            "modelid": "RDM002",
            "name": "RDM002 44",
            "state": {
                "expectedeventduration": 400,
                "expectedrotation": 75,
                "lastupdated": "2022-07-03T11:37:49.586",
                "rotaryevent": 2,
            },
            "swversion": "2.59.19",
            "type": "ZHARelativeRotary",
            "uniqueid": "xx:xx:xx:xx:xx:xx:xx:xx-14-fc00",
        }
    ],
)
async def test_deconz_relative_rotary_events(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry_setup: MockConfigEntry,
    sensor_ws_data: WebsocketDataType,
) -> None:
    """Test successful creation of deconz relative rotary events."""
    assert len(hass.states.async_all()) == 1
    assert (
        len(
            dr.async_entries_for_config_entry(
                device_registry, config_entry_setup.entry_id
            )
        )
        == 3
    )

    device = device_registry.async_get_device(
        identifiers={(DECONZ_DOMAIN, "xx:xx:xx:xx:xx:xx:xx:xx")}
    )

    captured_events = async_capture_events(hass, CONF_DECONZ_RELATIVE_ROTARY_EVENT)

    for rotary_event, duration, rotation in ((1, 100, 50), (2, 200, -50)):
        event_changed_sensor = {
            "state": {
                "rotaryevent": rotary_event,
                "expectedeventduration": duration,
                "expectedrotation": rotation,
            }
        }
        await sensor_ws_data(event_changed_sensor)

        assert len(captured_events) == 1
        assert captured_events[0].data == {
            CONF_ID: "rdm002_44",
            CONF_UNIQUE_ID: "xx:xx:xx:xx:xx:xx:xx:xx",
            CONF_DEVICE_ID: device.id,
            CONF_EVENT: RELATIVE_ROTARY_DECONZ_TO_EVENT[rotary_event],
            ATTR_DURATION: duration,
            ATTR_ROTATION: rotation,
        }
        captured_events.clear()

    # Unsupported relative rotary event

    await sensor_ws_data({"name": "123"})
    assert len(captured_events) == 0


@pytest.mark.parametrize(
    "sensor_payload",
    [
        {
            "1": {
                "name": "Switch 1 no unique id",
                "type": "ZHASwitch",
                "state": {"buttonevent": 1000},
                "config": {},
            },
            "2": {
                "name": "Switch 2 bad unique id",
                "type": "ZHASwitch",
                "state": {"buttonevent": 1000},
                "config": {"battery": 100},
                "uniqueid": "00:00-00",
            },
        }
    ],
)
async def test_deconz_events_bad_unique_id(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    config_entry_setup: MockConfigEntry,
) -> None:
    """Verify no devices are created if unique id is bad or missing."""
    assert len(hass.states.async_all()) == 1
    assert (
        len(
            dr.async_entries_for_config_entry(
                device_registry, config_entry_setup.entry_id
            )
        )
        == 2
    )
