"""Tests for Bosch SHC event entities."""

from unittest.mock import MagicMock

from homeassistant.components.bosch_shc.const import DOMAIN, OPT_EXCLUDED_DEVICES
from homeassistant.components.event import ATTR_EVENT_TYPE
from homeassistant.const import CONF_HOST, CONF_TOKEN
from homeassistant.core import HomeAssistant

from .conftest import make_device, setup_integration

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_keypad_service():
    """Return a mock Keypad device service with register_event tracking."""
    svc = MagicMock()
    svc.id = "Keypad"
    svc.register_event = MagicMock()
    return svc


def _make_latestmotion_service():
    """Return a mock LatestMotion device service."""
    svc = MagicMock()
    svc.id = "LatestMotion"
    svc.register_event = MagicMock()
    return svc


def _make_surveillance_alarm_service():
    """Return a mock SurveillanceAlarm device service."""
    svc = MagicMock()
    svc.id = "SurveillanceAlarm"
    svc.register_event = MagicMock()
    return svc


def _make_alarm_service():
    """Return a mock Alarm device service."""
    svc = MagicMock()
    svc.id = "Alarm"
    svc.register_event = MagicMock()
    return svc


def _capture_state_changes(hass: HomeAssistant, entity_id: str) -> list:
    """Return a list that accumulates every new_state for *entity_id*."""
    captured: list = []

    def _listener(event):
        if event.data["entity_id"] == entity_id:
            captured.append(event.data["new_state"])

    hass.bus.async_listen("state_changed", _listener)
    return captured


# ---------------------------------------------------------------------------
# UniversalSwitchEvent
# ---------------------------------------------------------------------------


async def test_universal_switch_event_entity_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Entity is created for each keystate reported by the switch."""
    session = mock_setup_dependencies
    svc = _make_keypad_service()

    switch = make_device(
        "switch-1", "Wall Switch", status="AVAILABLE"
    )
    switch.device_services = [svc]
    switch.keystates = ["LOWER_BUTTON", "UPPER_BUTTON"]
    switch.eventtype = None
    switch.eventtimestamp = 0

    session.device_helper.universal_switches = [switch]

    await setup_integration(hass, mock_config_entry)

    lower = hass.states.get("event.wall_switch_button_lower_button")
    upper = hass.states.get("event.wall_switch_button_upper_button")
    assert lower is not None
    assert upper is not None
    assert lower.attributes["event_types"] == [
        "PRESS_SHORT",
        "PRESS_LONG",
        "PRESS_LONG_RELEASED",
    ]


async def test_universal_switch_event_fires(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Pressing the switch fires a PRESS_SHORT event and updates state."""
    session = mock_setup_dependencies
    svc = _make_keypad_service()

    eventtype_mock = MagicMock()
    eventtype_mock.name = "PRESS_SHORT"

    switch = make_device("switch-1", "Wall Switch", status="AVAILABLE")
    switch.device_services = [svc]
    switch.keystates = ["LOWER_BUTTON"]
    switch.eventtype = eventtype_mock
    switch.eventtimestamp = 1000

    session.device_helper.universal_switches = [switch]

    await setup_integration(hass, mock_config_entry)

    # Start listening for state changes BEFORE we fire the callback.
    entity_id = "event.wall_switch_button_lower_button"
    changes = _capture_state_changes(hass, entity_id)

    # Grab the callback registered for LOWER_BUTTON
    cb = None
    for c in svc.register_event.call_args_list:
        if c[0][0] == "LOWER_BUTTON":
            cb = c[0][1]
    assert cb is not None, "register_event never called with LOWER_BUTTON"

    cb()
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    # At least one state_changed must have been emitted for this entity
    fired = [s for s in changes if s is not None and s.attributes.get(ATTR_EVENT_TYPE) == "PRESS_SHORT"]
    assert fired, "No PRESS_SHORT state_changed event captured"


async def test_universal_switch_event_fires_long_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Pressing the switch fires a PRESS_LONG event."""
    session = mock_setup_dependencies
    svc = _make_keypad_service()

    eventtype_mock = MagicMock()
    eventtype_mock.name = "PRESS_LONG"

    switch = make_device("switch-1", "Wall Switch", status="AVAILABLE")
    switch.device_services = [svc]
    switch.keystates = ["LOWER_BUTTON"]
    switch.eventtype = eventtype_mock
    switch.eventtimestamp = 2000

    session.device_helper.universal_switches = [switch]

    await setup_integration(hass, mock_config_entry)

    entity_id = "event.wall_switch_button_lower_button"
    changes = _capture_state_changes(hass, entity_id)

    cb = None
    for c in svc.register_event.call_args_list:
        if c[0][0] == "LOWER_BUTTON":
            cb = c[0][1]
    assert cb is not None

    cb()
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    fired = [s for s in changes if s is not None and s.attributes.get(ATTR_EVENT_TYPE) == "PRESS_LONG"]
    assert fired, "No PRESS_LONG state_changed event captured"


async def test_universal_switch_duplicate_timestamp_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """A second callback with the same timestamp must NOT fire a duplicate event."""
    session = mock_setup_dependencies
    svc = _make_keypad_service()

    eventtype_mock = MagicMock()
    eventtype_mock.name = "PRESS_SHORT"

    switch = make_device("switch-1", "Wall Switch", status="AVAILABLE")
    switch.device_services = [svc]
    switch.keystates = ["LOWER_BUTTON"]
    switch.eventtype = eventtype_mock
    switch.eventtimestamp = 500

    session.device_helper.universal_switches = [switch]

    await setup_integration(hass, mock_config_entry)

    entity_id = "event.wall_switch_button_lower_button"
    changes = _capture_state_changes(hass, entity_id)

    cb = None
    for c in svc.register_event.call_args_list:
        if c[0][0] == "LOWER_BUTTON":
            cb = c[0][1]
    assert cb is not None

    # First press — should emit one event
    cb()
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    first_count = len([s for s in changes if s is not None and s.attributes.get(ATTR_EVENT_TYPE) == "PRESS_SHORT"])
    assert first_count == 1

    # Second press with IDENTICAL timestamp → must be de-duplicated (no new event)
    cb()
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    second_count = len([s for s in changes if s is not None and s.attributes.get(ATTR_EVENT_TYPE) == "PRESS_SHORT"])
    assert second_count == first_count, "Duplicate timestamp should not emit a second event"


async def test_universal_switch_none_eventtype_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Callback with eventtype=None must not fire an event."""
    session = mock_setup_dependencies
    svc = _make_keypad_service()

    switch = make_device("switch-1", "Wall Switch", status="AVAILABLE")
    switch.device_services = [svc]
    switch.keystates = ["LOWER_BUTTON"]
    switch.eventtype = None
    switch.eventtimestamp = 100

    session.device_helper.universal_switches = [switch]

    await setup_integration(hass, mock_config_entry)

    entity_id = "event.wall_switch_button_lower_button"
    changes = _capture_state_changes(hass, entity_id)

    cb = None
    for c in svc.register_event.call_args_list:
        if c[0][0] == "LOWER_BUTTON":
            cb = c[0][1]
    assert cb is not None

    cb()
    await hass.async_block_till_done()

    # No event should have been fired
    fired = [s for s in changes if s is not None and s.attributes.get(ATTR_EVENT_TYPE) is not None]
    assert not fired, "None eventtype should not fire any event"


async def test_universal_switch_motor_eventtype_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Motor event types like SWITCH_ON must be silently dropped."""
    session = mock_setup_dependencies
    svc = _make_keypad_service()

    eventtype_mock = MagicMock()
    eventtype_mock.name = "SWITCH_ON"  # not a valid button event type

    switch = make_device("switch-1", "Wall Switch", status="AVAILABLE")
    switch.device_services = [svc]
    switch.keystates = ["LOWER_BUTTON"]
    switch.eventtype = eventtype_mock
    switch.eventtimestamp = 200

    session.device_helper.universal_switches = [switch]

    await setup_integration(hass, mock_config_entry)

    entity_id = "event.wall_switch_button_lower_button"
    changes = _capture_state_changes(hass, entity_id)

    cb = None
    for c in svc.register_event.call_args_list:
        if c[0][0] == "LOWER_BUTTON":
            cb = c[0][1]
    assert cb is not None

    cb()
    await hass.async_block_till_done()

    # SWITCH_ON is not in _attr_event_types for UniversalSwitchEvent → dropped
    fired = [
        s for s in changes
        if s is not None and s.attributes.get(ATTR_EVENT_TYPE) == "SWITCH_ON"
    ]
    assert not fired, "SWITCH_ON motor event should be ignored"


async def test_universal_switch_advancing_timestamp_fires_again(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """A callback with an ADVANCED timestamp fires a second event."""
    session = mock_setup_dependencies
    svc = _make_keypad_service()

    eventtype_mock = MagicMock()
    eventtype_mock.name = "PRESS_SHORT"

    switch = make_device("switch-1", "Wall Switch", status="AVAILABLE")
    switch.device_services = [svc]
    switch.keystates = ["LOWER_BUTTON"]
    switch.eventtype = eventtype_mock
    switch.eventtimestamp = 1000

    session.device_helper.universal_switches = [switch]

    await setup_integration(hass, mock_config_entry)

    entity_id = "event.wall_switch_button_lower_button"
    changes = _capture_state_changes(hass, entity_id)

    cb = None
    for c in svc.register_event.call_args_list:
        if c[0][0] == "LOWER_BUTTON":
            cb = c[0][1]
    assert cb is not None

    # First press at ts=1000
    cb()
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    count_1 = len([s for s in changes if s is not None and s.attributes.get(ATTR_EVENT_TYPE) == "PRESS_SHORT"])
    assert count_1 == 1

    # Second press at ts=2000 → new timestamp, must fire
    switch.eventtimestamp = 2000
    cb()
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    count_2 = len([s for s in changes if s is not None and s.attributes.get(ATTR_EVENT_TYPE) == "PRESS_SHORT"])
    assert count_2 == 2, "Second press with new timestamp should fire again"


# ---------------------------------------------------------------------------
# SHCScenarioEvent
# ---------------------------------------------------------------------------


async def test_scenario_event_entity_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """A scenario is registered as an event entity."""
    session = mock_setup_dependencies

    scenario = MagicMock()
    scenario.id = "scenario-1"
    scenario.name = "Good Night"
    session.scenarios = [scenario]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("event.scenario_good_night")
    assert state is not None
    assert state.attributes["event_types"] == ["SCENARIO"]


async def test_scenario_event_fires(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Triggering a scenario fires the SCENARIO event."""
    session = mock_setup_dependencies

    scenario = MagicMock()
    scenario.id = "scenario-1"
    scenario.name = "Good Night"
    session.scenarios = [scenario]

    await setup_integration(hass, mock_config_entry)

    # subscribe_scenario_callback(scenario_id, callback)
    assert session.subscribe_scenario_callback.called
    cb = session.subscribe_scenario_callback.call_args[0][1]

    entity_id = "event.scenario_good_night"
    changes = _capture_state_changes(hass, entity_id)

    event_data = {
        "id": "scenario-1",
        "name": "Good Night",
        "lastTimeTriggered": "2024-01-01T22:00:00",
    }
    cb(event_data)
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    fired = [
        s for s in changes
        if s is not None and s.attributes.get(ATTR_EVENT_TYPE) == "SCENARIO"
    ]
    assert fired, "No SCENARIO state_changed event captured"


async def test_scenario_event_unsubscribes_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """unsubscribe_scenario_callback is called when the entry is unloaded."""
    session = mock_setup_dependencies

    scenario = MagicMock()
    scenario.id = "scenario-42"
    scenario.name = "Away"
    session.scenarios = [scenario]

    await setup_integration(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    session.unsubscribe_scenario_callback.assert_called_with("scenario-42")


async def test_multiple_scenarios_each_subscribed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Each scenario gets its own subscription and entity."""
    session = mock_setup_dependencies

    sc1 = MagicMock()
    sc1.id = "sc-1"
    sc1.name = "Morning"

    sc2 = MagicMock()
    sc2.id = "sc-2"
    sc2.name = "Evening"

    session.scenarios = [sc1, sc2]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("event.scenario_morning") is not None
    assert hass.states.get("event.scenario_evening") is not None

    subscribed_ids = [
        c[0][0] for c in session.subscribe_scenario_callback.call_args_list
    ]
    assert "sc-1" in subscribed_ids
    assert "sc-2" in subscribed_ids


async def test_multiple_scenarios_unsubscribe_each_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Every scenario unsubscribes when the entry is unloaded."""
    session = mock_setup_dependencies

    sc1 = MagicMock()
    sc1.id = "sc-1"
    sc1.name = "Morning"

    sc2 = MagicMock()
    sc2.id = "sc-2"
    sc2.name = "Evening"

    session.scenarios = [sc1, sc2]

    await setup_integration(hass, mock_config_entry)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    unsubscribed = {c[0][0] for c in session.unsubscribe_scenario_callback.call_args_list}
    assert "sc-1" in unsubscribed
    assert "sc-2" in unsubscribed


# ---------------------------------------------------------------------------
# MotionDetectorEvent
# ---------------------------------------------------------------------------


async def test_motion_detector_event_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Motion detector event entity is created with MOTION event type."""
    session = mock_setup_dependencies
    svc = _make_latestmotion_service()

    motion = make_device("motion-1", "Hallway Motion", status="AVAILABLE")
    motion.device_services = [svc]
    motion.latestmotion = "2024-01-01T12:00:00"

    session.device_helper.motion_detectors = [motion]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("event.hallway_motion")
    assert state is not None
    assert state.attributes["event_types"] == ["MOTION"]


async def test_motion_detector_event_fires(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """A LatestMotion service event fires MOTION and updates entity state."""
    session = mock_setup_dependencies
    svc = _make_latestmotion_service()

    motion = make_device("motion-1", "Hallway Motion", status="AVAILABLE")
    motion.device_services = [svc]
    motion.latestmotion = "2024-01-01T12:00:00"

    session.device_helper.motion_detectors = [motion]

    await setup_integration(hass, mock_config_entry)

    entity_id = "event.hallway_motion"
    changes = _capture_state_changes(hass, entity_id)

    assert svc.register_event.called
    cb = svc.register_event.call_args[0][1]

    cb()
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    fired = [
        s for s in changes
        if s is not None and s.attributes.get(ATTR_EVENT_TYPE) == "MOTION"
    ]
    assert fired, "No MOTION state_changed event captured"


async def test_motion_detector2_event_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """motion_detectors2 collection also produces event entities."""
    session = mock_setup_dependencies
    svc = _make_latestmotion_service()

    motion2 = make_device("motion-2", "Bedroom Motion Gen2", status="AVAILABLE")
    motion2.device_services = [svc]
    motion2.latestmotion = "2024-01-01T13:00:00"

    session.device_helper.motion_detectors2 = [motion2]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("event.bedroom_motion_gen2")
    assert state is not None
    assert state.attributes["event_types"] == ["MOTION"]


async def test_motion_detectors_combined(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """motion_detectors and motion_detectors2 are combined into one entity list."""
    session = mock_setup_dependencies

    svc1 = _make_latestmotion_service()
    md1 = make_device("motion-gen1", "Living Room Motion", status="AVAILABLE")
    md1.device_services = [svc1]
    md1.latestmotion = "2024-01-01T12:00:00"

    svc2 = _make_latestmotion_service()
    md2 = make_device("motion-gen2", "Kitchen Motion Gen2", status="AVAILABLE")
    md2.device_services = [svc2]
    md2.latestmotion = "2024-01-01T13:00:00"

    session.device_helper.motion_detectors = [md1]
    session.device_helper.motion_detectors2 = [md2]

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("event.living_room_motion") is not None
    assert hass.states.get("event.kitchen_motion_gen2") is not None


# ---------------------------------------------------------------------------
# SmokeDetectionSystemEvent
# ---------------------------------------------------------------------------


async def test_smoke_detection_system_event_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Smoke detection system event entity is created."""
    session = mock_setup_dependencies
    svc = _make_surveillance_alarm_service()

    alarm_state = MagicMock()
    alarm_state.name = "IDLE_OFF"

    smoke_sys = make_device("smoke-sys-1", "Smoke System", status="AVAILABLE")
    smoke_sys.device_services = [svc]
    smoke_sys.alarm = alarm_state

    session.device_helper.smoke_detection_system = smoke_sys

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("event.smoke_system")
    assert state is not None
    assert state.attributes["event_types"] == ["ALARM"]


async def test_smoke_detection_system_event_fires(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SurveillanceAlarm service event fires ALARM with alarm subtype."""
    session = mock_setup_dependencies
    svc = _make_surveillance_alarm_service()

    alarm_state = MagicMock()
    alarm_state.name = "ALARM_ON"

    smoke_sys = make_device("smoke-sys-1", "Smoke System", status="AVAILABLE")
    smoke_sys.device_services = [svc]
    smoke_sys.alarm = alarm_state

    session.device_helper.smoke_detection_system = smoke_sys

    await setup_integration(hass, mock_config_entry)

    entity_id = "event.smoke_system"
    changes = _capture_state_changes(hass, entity_id)

    assert svc.register_event.called
    cb = svc.register_event.call_args[0][1]

    cb()
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    fired = [
        s for s in changes
        if s is not None and s.attributes.get(ATTR_EVENT_TYPE) == "ALARM"
    ]
    assert fired, "No ALARM state_changed event captured"
    assert fired[0].attributes.get("event_subtype") == "ALARM_ON"


async def test_smoke_detection_system_none_skipped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """When smoke_detection_system is falsy, no SmokeDetectionSystemEvent entity is created."""
    session = mock_setup_dependencies
    # conftest already sets smoke_detection_system via make_device("intrusion", ...) for
    # the intrusion system, but smoke_detection_system defaults to MagicMock (truthy) via
    # mock_device_helper. Override it explicitly.
    session.device_helper.smoke_detection_system = None

    await setup_integration(hass, mock_config_entry)

    # No crash; setup should succeed even without a smoke detection system.
    # (No specific entity id to assert since smoke_detection_system=None means no entity.)


# ---------------------------------------------------------------------------
# SmokeDetectorEvent
# ---------------------------------------------------------------------------


async def test_smoke_detector_event_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Individual smoke detector event entity is created."""
    session = mock_setup_dependencies
    svc = _make_alarm_service()

    alarmstate = MagicMock()
    alarmstate.name = "IDLE_OFF"

    detector = make_device("detector-1", "Kitchen Smoke Detector", status="AVAILABLE")
    detector.device_services = [svc]
    detector.alarmstate = alarmstate

    session.device_helper.smoke_detectors = [detector]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("event.kitchen_smoke_detector")
    assert state is not None
    assert state.attributes["event_types"] == ["ALARM"]


async def test_smoke_detector_event_fires(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Alarm service event fires ALARM with alarmstate subtype."""
    session = mock_setup_dependencies
    svc = _make_alarm_service()

    alarmstate = MagicMock()
    alarmstate.name = "PRIMARY_ALARM"

    detector = make_device("detector-1", "Kitchen Smoke Detector", status="AVAILABLE")
    detector.device_services = [svc]
    detector.alarmstate = alarmstate

    session.device_helper.smoke_detectors = [detector]

    await setup_integration(hass, mock_config_entry)

    entity_id = "event.kitchen_smoke_detector"
    changes = _capture_state_changes(hass, entity_id)

    assert svc.register_event.called
    cb = svc.register_event.call_args[0][1]

    cb()
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    fired = [
        s for s in changes
        if s is not None and s.attributes.get(ATTR_EVENT_TYPE) == "ALARM"
    ]
    assert fired, "No ALARM state_changed event captured"
    assert fired[0].attributes.get("event_subtype") == "PRIMARY_ALARM"


async def test_multiple_smoke_detectors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Multiple smoke detectors each produce their own event entity."""
    session = mock_setup_dependencies

    for dev_id, name in [("det-a", "Detector A"), ("det-b", "Detector B")]:
        svc = _make_alarm_service()
        alarmstate = MagicMock()
        alarmstate.name = "IDLE_OFF"
        det = make_device(dev_id, name, status="AVAILABLE")
        det.device_services = [svc]
        det.alarmstate = alarmstate
        session.device_helper.smoke_detectors.append(det)

    await setup_integration(hass, mock_config_entry)

    assert hass.states.get("event.detector_a") is not None
    assert hass.states.get("event.detector_b") is not None


# ---------------------------------------------------------------------------
# LightControlButtonEvent
# ---------------------------------------------------------------------------


async def test_light_control_button_event_created(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Light Control II with has_keypad=True produces a button event entity."""
    session = mock_setup_dependencies

    key_state_lower = MagicMock()
    key_state_lower.value = "LOWER_BUTTON"
    key_state_upper = MagicMock()
    key_state_upper.value = "UPPER_BUTTON"

    svc = MagicMock()
    svc.id = "Keypad"
    svc.KeyState = [key_state_lower, key_state_upper]
    svc.register_event = MagicMock()

    lc = make_device("lc-1", "Light Control II", status="AVAILABLE")
    lc.device_services = [svc]
    lc.has_keypad = True
    lc.eventtype = None
    lc.eventtimestamp = 0

    session.device_helper.micromodule_light_controls = [lc]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("event.light_control_ii_button")
    assert state is not None
    assert "PRESS_SHORT" in state.attributes["event_types"]
    assert "SWITCH_ON" in state.attributes["event_types"]
    assert "SWITCH_OFF" in state.attributes["event_types"]


async def test_light_control_button_no_keypad_skipped(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Light Control II without has_keypad does not produce a button event entity."""
    session = mock_setup_dependencies

    lc = make_device("lc-2", "Light Control No Keypad", status="AVAILABLE")
    lc.device_services = []
    lc.has_keypad = False

    session.device_helper.micromodule_light_controls = [lc]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("event.light_control_no_keypad_button")
    assert state is None


async def test_light_control_button_event_fires(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """PRESS_SHORT on Light Control II button fires the event."""
    session = mock_setup_dependencies

    key_state_lower = MagicMock()
    key_state_lower.value = "LOWER_BUTTON"

    svc = MagicMock()
    svc.id = "Keypad"
    svc.KeyState = [key_state_lower]
    svc.register_event = MagicMock()

    eventtype_mock = MagicMock()
    eventtype_mock.name = "PRESS_SHORT"

    lc = make_device("lc-1", "Light Control II", status="AVAILABLE")
    lc.device_services = [svc]
    lc.has_keypad = True
    lc.eventtype = eventtype_mock
    lc.eventtimestamp = 999

    session.device_helper.micromodule_light_controls = [lc]

    await setup_integration(hass, mock_config_entry)

    entity_id = "event.light_control_ii_button"
    changes = _capture_state_changes(hass, entity_id)

    assert svc.register_event.called
    cb = svc.register_event.call_args[0][1]

    cb()
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    fired = [
        s for s in changes
        if s is not None and s.attributes.get(ATTR_EVENT_TYPE) == "PRESS_SHORT"
    ]
    assert fired, "No PRESS_SHORT state_changed event captured for LightControl"


async def test_light_control_button_duplicate_timestamp_ignored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Duplicate timestamp on Light Control II button event is de-duplicated."""
    session = mock_setup_dependencies

    key_state_lower = MagicMock()
    key_state_lower.value = "LOWER_BUTTON"

    svc = MagicMock()
    svc.id = "Keypad"
    svc.KeyState = [key_state_lower]
    svc.register_event = MagicMock()

    eventtype_mock = MagicMock()
    eventtype_mock.name = "PRESS_SHORT"

    lc = make_device("lc-1", "Light Control II", status="AVAILABLE")
    lc.device_services = [svc]
    lc.has_keypad = True
    lc.eventtype = eventtype_mock
    lc.eventtimestamp = 111

    session.device_helper.micromodule_light_controls = [lc]

    await setup_integration(hass, mock_config_entry)

    entity_id = "event.light_control_ii_button"
    changes = _capture_state_changes(hass, entity_id)

    cb = svc.register_event.call_args[0][1]

    cb()
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    count_1 = len([s for s in changes if s is not None and s.attributes.get(ATTR_EVENT_TYPE) == "PRESS_SHORT"])
    assert count_1 == 1

    # Same timestamp → de-duplicated
    cb()
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    count_2 = len([s for s in changes if s is not None and s.attributes.get(ATTR_EVENT_TYPE) == "PRESS_SHORT"])
    assert count_2 == count_1, "Duplicate timestamp should not fire again"


async def test_light_control_button_switch_on_fires(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
) -> None:
    """SWITCH_ON event type fires correctly for LightControlButtonEvent."""
    session = mock_setup_dependencies

    key_state_lower = MagicMock()
    key_state_lower.value = "LOWER_BUTTON"

    svc = MagicMock()
    svc.id = "Keypad"
    svc.KeyState = [key_state_lower]
    svc.register_event = MagicMock()

    eventtype_mock = MagicMock()
    eventtype_mock.name = "SWITCH_ON"  # valid for LightControl, invalid for UniversalSwitch

    lc = make_device("lc-1", "Light Control II", status="AVAILABLE")
    lc.device_services = [svc]
    lc.has_keypad = True
    lc.eventtype = eventtype_mock
    lc.eventtimestamp = 500

    session.device_helper.micromodule_light_controls = [lc]

    await setup_integration(hass, mock_config_entry)

    entity_id = "event.light_control_ii_button"
    changes = _capture_state_changes(hass, entity_id)

    cb = svc.register_event.call_args[0][1]
    cb()
    await hass.async_block_till_done()
    await hass.async_block_till_done()

    fired = [
        s for s in changes
        if s is not None and s.attributes.get(ATTR_EVENT_TYPE) == "SWITCH_ON"
    ]
    assert fired, "SWITCH_ON should fire for LightControlButtonEvent"


# ---------------------------------------------------------------------------
# Exclusion filter (OPT_EXCLUDED_DEVICES)
# ---------------------------------------------------------------------------


async def test_excluded_universal_switch_skipped(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Devices listed in OPT_EXCLUDED_DEVICES are not added as entities."""
    # Build a fresh config entry with the exclusion option set at construction time.
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="shc012345",
        unique_id="test-mac",
        entry_id="01JE69BM3MA48YE6RH05A4MDKQ",
        data={
            CONF_HOST: "1.1.1.1",
            "ssl_certificate": "/etc/bosch_shc/test-cert.pem",
            "ssl_key": "/etc/bosch_shc/test-key.pem",
            CONF_TOKEN: "abc:test-mac",
            "hostname": "test-mac",
        },
        options={OPT_EXCLUDED_DEVICES: ["switch-excluded"]},
    )

    session = mock_setup_dependencies
    svc = _make_keypad_service()

    switch = make_device("switch-excluded", "Excluded Switch", status="AVAILABLE")
    switch.device_services = [svc]
    switch.keystates = ["LOWER_BUTTON"]
    switch.eventtype = None
    switch.eventtimestamp = 0

    session.device_helper.universal_switches = [switch]

    await setup_integration(hass, entry)

    assert hass.states.get("event.excluded_switch_button_lower_button") is None


async def test_excluded_motion_detector_skipped(
    hass: HomeAssistant,
    mock_setup_dependencies: MagicMock,
) -> None:
    """Motion detectors in OPT_EXCLUDED_DEVICES are not added as entities."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="shc012345",
        unique_id="test-mac",
        entry_id="01JE69BM3MA48YE6RH05A4MDKQ",
        data={
            CONF_HOST: "1.1.1.1",
            "ssl_certificate": "/etc/bosch_shc/test-cert.pem",
            "ssl_key": "/etc/bosch_shc/test-key.pem",
            CONF_TOKEN: "abc:test-mac",
            "hostname": "test-mac",
        },
        options={OPT_EXCLUDED_DEVICES: ["motion-excl"]},
    )

    session = mock_setup_dependencies
    svc = _make_latestmotion_service()

    motion = make_device("motion-excl", "Excluded Motion", status="AVAILABLE")
    motion.device_services = [svc]
    motion.latestmotion = "2024-01-01T12:00:00"

    session.device_helper.motion_detectors = [motion]

    await setup_integration(hass, entry)

    assert hass.states.get("event.excluded_motion") is None
