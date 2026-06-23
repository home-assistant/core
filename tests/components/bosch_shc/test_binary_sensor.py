"""Tests for the bosch_shc binary_sensor platform."""

from datetime import timedelta
import json
from unittest.mock import AsyncMock, MagicMock

from boschshcpy import (
    SHCBatteryDevice,
    SHCShutterContact,
    SHCShutterContact2Plus,
    SHCSmokeDetectionSystem,
    SHCSmokeDetector,
    SHCWaterLeakageSensor,
)

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.bosch_shc.binary_sensor import TwinguardAlarmTracker
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import make_device, setup_integration

from tests.common import MockConfigEntry

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(service_id: str) -> MagicMock:
    """Return a mock SHC service with subscribe/unsubscribe stubs."""
    svc = MagicMock()
    svc.id = service_id
    svc.subscribe_callback = MagicMock()
    svc.unsubscribe_callback = MagicMock()
    return svc


def _avail_device(device_id: str, name: str, **kwargs) -> MagicMock:
    """Wrapper around make_device that always sets status='AVAILABLE'."""
    return make_device(device_id=device_id, name=name, status="AVAILABLE", **kwargs)


# ---------------------------------------------------------------------------
# ShutterContactSensor
# ---------------------------------------------------------------------------


async def test_shutter_contact_open(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """ShutterContactSensor reports 'on' when contact is OPEN."""
    device = _avail_device(
        device_id="sc-1",
        name="Front Door",
        state=SHCShutterContact.ShutterContactService.State.OPEN,
        device_class="ENTRANCE_DOOR",
        supports_batterylevel=False,
    )
    mock_session.device_helper.shutter_contacts = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.front_door")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.DOOR


async def test_shutter_contact_closed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """ShutterContactSensor reports 'off' when contact is CLOSED."""
    device = _avail_device(
        device_id="sc-2",
        name="Bedroom Window",
        state=SHCShutterContact.ShutterContactService.State.CLOSED,
        device_class="REGULAR_WINDOW",
        supports_batterylevel=False,
    )
    mock_session.device_helper.shutter_contacts = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.bedroom_window")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.WINDOW


async def test_shutter_contact_device_class_french_window(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """FRENCH_WINDOW maps to DOOR device class."""
    device = _avail_device(
        device_id="sc-3",
        name="Balcony Door",
        state=SHCShutterContact.ShutterContactService.State.CLOSED,
        device_class="FRENCH_WINDOW",
        supports_batterylevel=False,
    )
    mock_session.device_helper.shutter_contacts = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.balcony_door")
    assert state is not None
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.DOOR


async def test_shutter_contact_generic_device_class(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """GENERIC device_class (and any unknown) maps to WINDOW."""
    device = _avail_device(
        device_id="sc-4",
        name="Generic Contact",
        state=SHCShutterContact.ShutterContactService.State.CLOSED,
        device_class="GENERIC",
        supports_batterylevel=False,
    )
    mock_session.device_helper.shutter_contacts = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.generic_contact")
    assert state is not None
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.WINDOW


# ---------------------------------------------------------------------------
# ShutterContact2 (in shutter_contacts2 list)
# ---------------------------------------------------------------------------


async def test_shutter_contact2_via_shutter_contacts2(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """Devices in shutter_contacts2 also produce ShutterContactSensor entities."""
    device = _avail_device(
        device_id="sc2-1",
        name="Side Window",
        state=SHCShutterContact.ShutterContactService.State.OPEN,
        device_class="REGULAR_WINDOW",
        supports_batterylevel=False,
    )
    # Not a SHCShutterContact2Plus, so no vibration sensor is added
    mock_session.device_helper.shutter_contacts2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.side_window")
    assert state is not None
    assert state.state == STATE_ON


# ---------------------------------------------------------------------------
# ShutterContactVibrationSensor
# ---------------------------------------------------------------------------


async def test_vibration_sensor_detected(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """ShutterContactVibrationSensor is 'on' when VIBRATION_DETECTED."""
    device = _avail_device(
        device_id="sc2plus-1",
        name="Plus Window",
        state=SHCShutterContact.ShutterContactService.State.CLOSED,
        device_class="REGULAR_WINDOW",
        vibrationsensor=SHCShutterContact2Plus.VibrationSensorService.State.VIBRATION_DETECTED,
        supports_batterylevel=False,
    )
    # Make isinstance check pass for SHCShutterContact2Plus
    device.__class__ = SHCShutterContact2Plus
    mock_session.device_helper.shutter_contacts2 = [device]

    await setup_integration(hass, mock_config_entry)

    vibration_state = hass.states.get("binary_sensor.plus_window_vibration")
    assert vibration_state is not None
    assert vibration_state.state == STATE_ON
    assert (
        vibration_state.attributes[ATTR_DEVICE_CLASS]
        == BinarySensorDeviceClass.VIBRATION
    )


async def test_vibration_sensor_no_vibration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """ShutterContactVibrationSensor is 'off' when NO_VIBRATION."""
    device = _avail_device(
        device_id="sc2plus-2",
        name="Quiet Window",
        state=SHCShutterContact.ShutterContactService.State.CLOSED,
        device_class="REGULAR_WINDOW",
        vibrationsensor=SHCShutterContact2Plus.VibrationSensorService.State.NO_VIBRATION,
        supports_batterylevel=False,
    )
    device.__class__ = SHCShutterContact2Plus
    mock_session.device_helper.shutter_contacts2 = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.quiet_window_vibration")
    assert state is not None
    assert state.state == STATE_OFF


# ---------------------------------------------------------------------------
# MotionDetectionSensor
# ---------------------------------------------------------------------------


async def test_motion_detection_sensor_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """MotionDetectionSensor is 'on' when latestmotion was within 4 minutes."""
    recent_ts = (dt_util.utcnow() - timedelta(seconds=30)).strftime(
        "%Y-%m-%dT%H:%M:%S.%f"
    )[:-3] + "Z"  # millisecond precision, trailing Z

    motion_svc = _make_service("LatestMotion")
    device = _avail_device(
        device_id="md-1",
        name="Living Room Motion",
        latestmotion=recent_ts,
        supports_batterylevel=False,
        device_services=[motion_svc],
    )
    mock_session.device_helper.motion_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.living_room_motion")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.MOTION
    assert "last_motion_detected" in state.attributes


async def test_motion_detection_sensor_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """MotionDetectionSensor is 'off' when latestmotion was more than 4 minutes ago."""
    old_ts = (dt_util.utcnow() - timedelta(minutes=5)).strftime(
        "%Y-%m-%dT%H:%M:%S.%f"
    )[:-3] + "Z"

    motion_svc = _make_service("LatestMotion")
    device = _avail_device(
        device_id="md-2",
        name="Hall Motion",
        latestmotion=old_ts,
        supports_batterylevel=False,
        device_services=[motion_svc],
    )
    mock_session.device_helper.motion_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.hall_motion")
    assert state is not None
    assert state.state == STATE_OFF


async def test_motion_detection_sensor_none_timestamp(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """MotionDetectionSensor returns 'off' when latestmotion is None."""
    motion_svc = _make_service("LatestMotion")
    device = _avail_device(
        device_id="md-3",
        name="Garage Motion",
        latestmotion=None,
        supports_batterylevel=False,
        device_services=[motion_svc],
    )
    mock_session.device_helper.motion_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.garage_motion")
    assert state is not None
    assert state.state == STATE_OFF


async def test_motion_detection_sensor_callback_subscribes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """MotionDetectionSensor subscribes a callback to the LatestMotion service."""
    recent_ts = (dt_util.utcnow() - timedelta(seconds=10)).strftime(
        "%Y-%m-%dT%H:%M:%S.%f"
    )[:-3] + "Z"

    motion_svc = _make_service("LatestMotion")
    captured_callbacks: dict = {}

    def _subscribe(key, cb):
        captured_callbacks[key] = cb

    motion_svc.subscribe_callback = _subscribe

    device = _avail_device(
        device_id="md-cb-1",
        name="Callback Motion",
        latestmotion=recent_ts,
        supports_batterylevel=False,
        device_services=[motion_svc],
    )
    mock_session.device_helper.motion_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    # The callback must be registered under <device_id>_eventlistener
    cb_key = "md-cb-1_eventlistener"
    assert cb_key in captured_callbacks, "subscribe_callback was not called"


async def test_motion_detection_sensor_unsubscribes_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """MotionDetectionSensor calls unsubscribe_callback on config-entry unload."""
    motion_svc = _make_service("LatestMotion")
    subscribed_keys: list[str] = []
    unsubscribed_keys: list[str] = []

    def _subscribe(key, cb):
        subscribed_keys.append(key)

    def _unsubscribe(key):
        unsubscribed_keys.append(key)

    motion_svc.subscribe_callback = _subscribe
    motion_svc.unsubscribe_callback = _unsubscribe

    device = _avail_device(
        device_id="md-unsub-1",
        name="Unsub Motion",
        latestmotion=None,
        supports_batterylevel=False,
        device_services=[motion_svc],
    )
    mock_session.device_helper.motion_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    # Unload the config entry — async_will_remove_from_hass must fire
    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert "md-unsub-1_eventlistener" in subscribed_keys
    assert "md-unsub-1_eventlistener" in unsubscribed_keys


# ---------------------------------------------------------------------------
# SmokeDetectorSensor
# ---------------------------------------------------------------------------


async def test_smoke_detector_alarm_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """SmokeDetectorSensor is 'on' for PRIMARY_ALARM."""
    alarm_svc = _make_service("Alarm")

    smoke_check_state = MagicMock()
    smoke_check_state.name = "SMOKE_TEST_OK"

    device = _avail_device(
        device_id="sd-1",
        name="Kitchen Smoke",
        alarmstate=SHCSmokeDetector.AlarmService.State.PRIMARY_ALARM,
        smokedetectorcheck_state=smoke_check_state,
        supports_batterylevel=False,
        device_services=[alarm_svc],
    )
    mock_session.device_helper.smoke_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.kitchen_smoke")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.SMOKE
    assert state.attributes["alarmstate"] == "PRIMARY_ALARM"


async def test_smoke_detector_secondary_alarm_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """SmokeDetectorSensor is 'on' for SECONDARY_ALARM."""
    alarm_svc = _make_service("Alarm")

    smoke_check_state = MagicMock()
    smoke_check_state.name = "SMOKE_TEST_REQUESTED"

    device = _avail_device(
        device_id="sd-2",
        name="Hallway Smoke",
        alarmstate=SHCSmokeDetector.AlarmService.State.SECONDARY_ALARM,
        smokedetectorcheck_state=smoke_check_state,
        supports_batterylevel=False,
        device_services=[alarm_svc],
    )
    mock_session.device_helper.smoke_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.hallway_smoke")
    assert state is not None
    assert state.state == STATE_ON


async def test_smoke_detector_intrusion_alarm_is_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """INTRUSION_ALARM must NOT be treated as a smoke alarm (issue #191)."""
    alarm_svc = _make_service("Alarm")

    smoke_check_state = MagicMock()
    smoke_check_state.name = "SMOKE_TEST_OK"

    device = _avail_device(
        device_id="sd-3",
        name="Office Smoke",
        alarmstate=SHCSmokeDetector.AlarmService.State.INTRUSION_ALARM,
        smokedetectorcheck_state=smoke_check_state,
        supports_batterylevel=False,
        device_services=[alarm_svc],
    )
    mock_session.device_helper.smoke_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.office_smoke")
    assert state is not None
    assert state.state == STATE_OFF  # INTRUSION_ALARM must not trigger smoke=on


async def test_smoke_detector_idle_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """SmokeDetectorSensor is 'off' when IDLE_OFF."""
    alarm_svc = _make_service("Alarm")

    smoke_check_state = MagicMock()
    smoke_check_state.name = "SMOKE_TEST_OK"

    device = _avail_device(
        device_id="sd-4",
        name="Bedroom Smoke",
        alarmstate=SHCSmokeDetector.AlarmService.State.IDLE_OFF,
        smokedetectorcheck_state=smoke_check_state,
        supports_batterylevel=False,
        device_services=[alarm_svc],
    )
    mock_session.device_helper.smoke_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.bedroom_smoke")
    assert state is not None
    assert state.state == STATE_OFF


async def test_smoke_detector_unsubscribes_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """SmokeDetectorSensor unsubscribes its Alarm service callback on unload."""
    alarm_svc = _make_service("Alarm")
    subscribed: list[str] = []
    unsubscribed: list[str] = []

    alarm_svc.subscribe_callback = lambda k, cb: subscribed.append(k)
    alarm_svc.unsubscribe_callback = lambda k: unsubscribed.append(k)

    smoke_check_state = MagicMock()
    smoke_check_state.name = "SMOKE_TEST_OK"

    device = _avail_device(
        device_id="sd-unsub-1",
        name="Unsub Smoke",
        alarmstate=SHCSmokeDetector.AlarmService.State.IDLE_OFF,
        smokedetectorcheck_state=smoke_check_state,
        supports_batterylevel=False,
        device_services=[alarm_svc],
    )
    mock_session.device_helper.smoke_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert "sd-unsub-1_eventlistener" in subscribed
    assert "sd-unsub-1_eventlistener" in unsubscribed


# ---------------------------------------------------------------------------
# WaterLeakageDetectorSensor
# ---------------------------------------------------------------------------


async def test_water_leakage_sensor_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """WaterLeakageDetectorSensor is 'on' when LEAKAGE_DETECTED."""
    push_state = MagicMock()
    push_state.name = "ENABLED"
    acoustic_state = MagicMock()
    acoustic_state.name = "ENABLED"

    device = _avail_device(
        device_id="wl-1",
        name="Basement Leak",
        leakage_state=SHCWaterLeakageSensor.WaterLeakageSensorService.State.LEAKAGE_DETECTED,
        push_notification_state=push_state,
        acoustic_signal_state=acoustic_state,
        supports_batterylevel=False,
    )
    mock_session.device_helper.water_leakage_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.basement_leak")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.MOISTURE
    assert state.attributes["push_notification_state"] == "ENABLED"
    assert state.attributes["acoustic_signal_state"] == "ENABLED"


async def test_water_leakage_sensor_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """WaterLeakageDetectorSensor is 'off' when NO_LEAKAGE."""
    push_state = MagicMock()
    push_state.name = "DISABLED"
    acoustic_state = MagicMock()
    acoustic_state.name = "DISABLED"

    device = _avail_device(
        device_id="wl-2",
        name="Kitchen Leak",
        leakage_state=SHCWaterLeakageSensor.WaterLeakageSensorService.State.NO_LEAKAGE,
        push_notification_state=push_state,
        acoustic_signal_state=acoustic_state,
        supports_batterylevel=False,
    )
    mock_session.device_helper.water_leakage_detectors = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.kitchen_leak")
    assert state is not None
    assert state.state == STATE_OFF


# ---------------------------------------------------------------------------
# BatterySensor
# ---------------------------------------------------------------------------


async def test_battery_sensor_ok(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """BatterySensor is 'off' (no problem) when battery is OK."""
    device = _avail_device(
        device_id="sc-bat-1",
        name="Battery Window",
        state=SHCShutterContact.ShutterContactService.State.CLOSED,
        device_class="REGULAR_WINDOW",
        batterylevel=SHCBatteryDevice.BatteryLevelService.State.OK,
        supports_batterylevel=True,
    )
    mock_session.device_helper.shutter_contacts = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.battery_window_battery")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.BATTERY


async def test_battery_sensor_low(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """BatterySensor is 'on' (problem) when battery is LOW_BATTERY."""
    device = _avail_device(
        device_id="sc-bat-2",
        name="Low Battery Door",
        state=SHCShutterContact.ShutterContactService.State.CLOSED,
        device_class="ENTRANCE_DOOR",
        batterylevel=SHCBatteryDevice.BatteryLevelService.State.LOW_BATTERY,
        supports_batterylevel=True,
    )
    mock_session.device_helper.shutter_contacts = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.low_battery_door_battery")
    assert state is not None
    assert state.state == STATE_ON


async def test_battery_sensor_critical_low(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """BatterySensor is 'on' when CRITICAL_LOW."""
    device = _avail_device(
        device_id="sc-bat-3",
        name="Critical Door",
        state=SHCShutterContact.ShutterContactService.State.CLOSED,
        device_class="ENTRANCE_DOOR",
        batterylevel=SHCBatteryDevice.BatteryLevelService.State.CRITICAL_LOW,
        supports_batterylevel=True,
    )
    mock_session.device_helper.shutter_contacts = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.critical_door_battery")
    assert state is not None
    assert state.state == STATE_ON


async def test_battery_sensor_not_available(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """BatterySensor is 'off' (not a problem) when battery state is NOT_AVAILABLE."""
    device = _avail_device(
        device_id="sc-bat-4",
        name="Unknown Battery Door",
        state=SHCShutterContact.ShutterContactService.State.CLOSED,
        device_class="ENTRANCE_DOOR",
        batterylevel=SHCBatteryDevice.BatteryLevelService.State.NOT_AVAILABLE,
        supports_batterylevel=True,
    )
    mock_session.device_helper.shutter_contacts = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.unknown_battery_door_battery")
    assert state is not None
    assert state.state == STATE_OFF


async def test_battery_sensor_entity_category(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """BatterySensor must have EntityCategory.DIAGNOSTIC."""
    device = _avail_device(
        device_id="sc-bat-cat",
        name="Cat Battery Door",
        state=SHCShutterContact.ShutterContactService.State.CLOSED,
        device_class="ENTRANCE_DOOR",
        batterylevel=SHCBatteryDevice.BatteryLevelService.State.OK,
        supports_batterylevel=True,
    )
    mock_session.device_helper.shutter_contacts = [device]

    await setup_integration(hass, mock_config_entry)

    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("binary_sensor.cat_battery_door_battery")
    assert entry is not None
    assert entry.entity_category == EntityCategory.DIAGNOSTIC


# ---------------------------------------------------------------------------
# SmokeDetectionSystemSensor
# ---------------------------------------------------------------------------


async def test_smoke_detection_system_alarm_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """SmokeDetectionSystemSensor is 'on' when alarm is ALARM_ON."""
    surveillance_svc = _make_service("SurveillanceAlarm")

    device = _avail_device(
        device_id="sds-1",
        name="Smoke System",
        alarm=SHCSmokeDetectionSystem.SurveillanceAlarmService.State.ALARM_ON,
        supports_batterylevel=False,
        device_services=[surveillance_svc],
    )
    mock_session.device_helper.smoke_detection_system = device
    # No twinguards — keeps the test simple
    mock_session.device_helper.twinguards = []

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.smoke_system")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.SMOKE
    assert state.attributes["alarm_state"] == "ALARM_ON"


async def test_smoke_detection_system_alarm_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """SmokeDetectionSystemSensor is 'off' when alarm is ALARM_OFF."""
    surveillance_svc = _make_service("SurveillanceAlarm")

    device = _avail_device(
        device_id="sds-2",
        name="Smoke System Off",
        alarm=SHCSmokeDetectionSystem.SurveillanceAlarmService.State.ALARM_OFF,
        supports_batterylevel=False,
        device_services=[surveillance_svc],
    )
    mock_session.device_helper.smoke_detection_system = device
    mock_session.device_helper.twinguards = []

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.smoke_system_off")
    assert state is not None
    assert state.state == STATE_OFF


async def test_smoke_detection_system_unsubscribes_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """SmokeDetectionSystemSensor unsubscribes SurveillanceAlarm callback on unload."""
    surveillance_svc = _make_service("SurveillanceAlarm")
    subscribed: list[str] = []
    unsubscribed: list[str] = []

    surveillance_svc.subscribe_callback = lambda k, cb: subscribed.append(k)
    surveillance_svc.unsubscribe_callback = lambda k: unsubscribed.append(k)

    device = _avail_device(
        device_id="sds-unsub-1",
        name="Unsub Smoke System",
        alarm=SHCSmokeDetectionSystem.SurveillanceAlarmService.State.ALARM_OFF,
        supports_batterylevel=False,
        device_services=[surveillance_svc],
    )
    mock_session.device_helper.smoke_detection_system = device
    mock_session.device_helper.twinguards = []

    await setup_integration(hass, mock_config_entry)

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert "sds-unsub-1_eventlistener" in subscribed
    assert "sds-unsub-1_eventlistener" in unsubscribed


# ---------------------------------------------------------------------------
# TwinguardSmokeAlarmSensor + TwinguardAlarmTracker
# ---------------------------------------------------------------------------


async def test_twinguard_smoke_alarm_sensor_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """TwinguardSmokeAlarmSensor is 'off' when not in active trigger ids."""
    surveillance_svc = _make_service("SurveillanceAlarm")

    sds_device = _avail_device(
        device_id="sds-tg-1",
        name="Twinguard System",
        alarm=SHCSmokeDetectionSystem.SurveillanceAlarmService.State.ALARM_OFF,
        supports_batterylevel=False,
        device_services=[surveillance_svc],
    )
    mock_session.device_helper.smoke_detection_system = sds_device

    tg_device = _avail_device(
        device_id="tg-1",
        name="Living Room Twinguard",
        supports_batterylevel=False,
    )
    mock_session.device_helper.twinguards = [tg_device]

    # async_refresh calls get_messages; mock the api
    mock_session.api = AsyncMock()
    mock_session.api.get_messages = AsyncMock(return_value=[])

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.living_room_twinguard_smoke")
    assert state is not None
    assert state.state == STATE_OFF
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.SMOKE


async def test_twinguard_smoke_alarm_sensor_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """TwinguardSmokeAlarmSensor is 'on' when get_messages reports triggerId matching device."""
    surveillance_svc = _make_service("SurveillanceAlarm")

    sds_device = _avail_device(
        device_id="sds-tg-2",
        name="Active System",
        alarm=SHCSmokeDetectionSystem.SurveillanceAlarmService.State.ALARM_ON,
        supports_batterylevel=False,
        device_services=[surveillance_svc],
    )
    mock_session.device_helper.smoke_detection_system = sds_device

    tg_device = _avail_device(
        device_id="tg-active-1",
        name="Bedroom Twinguard",
        supports_batterylevel=False,
    )
    mock_session.device_helper.twinguards = [tg_device]

    # Message whose triggerId matches the twinguard device id
    smoke_message = {
        "messageCode": {"name": "SMOKE_ALARM"},
        "sourceId": "sds-tg-2",
        "arguments": {
            "surveillanceEvents": [{"triggerId": "tg-active-1", "type": "ALARM_ON"}]
        },
    }
    mock_session.api = AsyncMock()
    mock_session.api.get_messages = AsyncMock(return_value=[smoke_message])

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.bedroom_twinguard_smoke")
    assert state is not None
    assert state.state == STATE_ON


# ---------------------------------------------------------------------------
# CallForHeatSensor
# ---------------------------------------------------------------------------


async def _setup_call_for_heat(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_session: MagicMock,
    has_demand: bool,
    device_id: str,
    name: str,
) -> None:
    """Helper: inject a climate_controls device and set up the integration.

    Sets session.room() to return a mock with a string name so the climate
    platform does not attempt to serialize a MagicMock during teardown.
    """
    room_mock = MagicMock()
    room_mock.name = "Test Room"
    mock_session.room = MagicMock(return_value=room_mock)

    device = _avail_device(
        device_id=device_id,
        name=name,
        has_demand=has_demand,
        supports_batterylevel=False,
        # room_id is needed by climate platform; use a deterministic string
        room_id="room-test",
    )
    mock_session.device_helper.climate_controls = [device]
    await setup_integration(hass, mock_config_entry)


async def test_call_for_heat_sensor_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """CallForHeatSensor is 'on' when has_demand is True."""
    await _setup_call_for_heat(
        hass, mock_config_entry, mock_session, True, "rcc-1", "Living Room Climate"
    )

    state = hass.states.get("binary_sensor.living_room_climate_call_for_heat")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.RUNNING


async def test_call_for_heat_sensor_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """CallForHeatSensor is 'off' when has_demand is False."""
    await _setup_call_for_heat(
        hass, mock_config_entry, mock_session, False, "rcc-2", "Bedroom Climate"
    )

    state = hass.states.get("binary_sensor.bedroom_climate_call_for_heat")
    assert state is not None
    assert state.state == STATE_OFF


async def test_call_for_heat_sensor_missing_attr(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """CallForHeatSensor gracefully defaults to 'off' when has_demand is absent."""
    room_mock = MagicMock()
    room_mock.name = "Test Room"
    mock_session.room = MagicMock(return_value=room_mock)

    device = _avail_device(
        device_id="rcc-3",
        name="Old Climate",
        supports_batterylevel=False,
        room_id="room-test",
    )
    # Deliberately remove has_demand from the MagicMock so getattr guard is exercised
    del device.has_demand

    mock_session.device_helper.climate_controls = [device]

    await setup_integration(hass, mock_config_entry)

    state = hass.states.get("binary_sensor.old_climate_call_for_heat")
    assert state is not None
    assert state.state == STATE_OFF


# ---------------------------------------------------------------------------
# OccupancyDetectionSensor + TamperSensor (from motion_detectors2)
# ---------------------------------------------------------------------------


async def test_motion_detector2_produces_occupancy_and_tamper(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """motion_detectors2 produces MotionDetectionSensor + OccupancyDetectionSensor + TamperSensor."""
    motion_svc = _make_service("LatestMotion")

    old_ts = (dt_util.utcnow() - timedelta(minutes=10)).strftime(
        "%Y-%m-%dT%H:%M:%S.%f"
    )[:-3] + "Z"

    device = _avail_device(
        device_id="md2-1",
        name="Office MD2",
        latestmotion=old_ts,
        occupied=True,
        last_occupancy_change_time="2024-01-01T10:00:00.000Z",
        was_tampered=False,
        last_tamper_time=None,
        supports_batterylevel=False,
        device_services=[motion_svc],
    )
    mock_session.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    # Motion sensor (off — old timestamp)
    motion_state = hass.states.get("binary_sensor.office_md2")
    assert motion_state is not None
    assert motion_state.state == STATE_OFF
    assert motion_state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.MOTION

    # Occupancy sensor (on — occupied=True)
    occ_state = hass.states.get("binary_sensor.office_md2_occupancy")
    assert occ_state is not None
    assert occ_state.state == STATE_ON
    assert occ_state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.OCCUPANCY
    assert occ_state.attributes["last_occupancy_change"] == "2024-01-01T10:00:00.000Z"

    # Tamper sensor (off — was_tampered=False)
    tamper_state = hass.states.get("binary_sensor.office_md2_tamper")
    assert tamper_state is not None
    assert tamper_state.state == STATE_OFF
    assert tamper_state.attributes[ATTR_DEVICE_CLASS] == BinarySensorDeviceClass.TAMPER


async def test_tamper_sensor_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """TamperSensor is 'on' when was_tampered is True."""
    motion_svc = _make_service("LatestMotion")

    old_ts = (dt_util.utcnow() - timedelta(minutes=10)).strftime(
        "%Y-%m-%dT%H:%M:%S.%f"
    )[:-3] + "Z"

    device = _avail_device(
        device_id="md2-tamper-1",
        name="Tampered Detector",
        latestmotion=old_ts,
        occupied=False,
        last_occupancy_change_time=None,
        was_tampered=True,
        last_tamper_time="2024-06-01T12:00:00.000Z",
        supports_batterylevel=False,
        device_services=[motion_svc],
    )
    mock_session.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    tamper_state = hass.states.get("binary_sensor.tampered_detector_tamper")
    assert tamper_state is not None
    assert tamper_state.state == STATE_ON
    assert tamper_state.attributes["last_tamper_time"] == "2024-06-01T12:00:00.000Z"


async def test_tamper_sensor_entity_category(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_setup_dependencies: MagicMock,
    mock_session: MagicMock,
) -> None:
    """TamperSensor must have EntityCategory.DIAGNOSTIC."""
    motion_svc = _make_service("LatestMotion")
    old_ts = (dt_util.utcnow() - timedelta(minutes=10)).strftime(
        "%Y-%m-%dT%H:%M:%S.%f"
    )[:-3] + "Z"

    device = _avail_device(
        device_id="md2-cat-1",
        name="Category Detector",
        latestmotion=old_ts,
        occupied=False,
        last_occupancy_change_time=None,
        was_tampered=False,
        last_tamper_time=None,
        supports_batterylevel=False,
        device_services=[motion_svc],
    )
    mock_session.device_helper.motion_detectors2 = [device]

    await setup_integration(hass, mock_config_entry)

    ent_reg = er.async_get(hass)
    entry = ent_reg.async_get("binary_sensor.category_detector_tamper")
    assert entry is not None
    assert entry.entity_category == EntityCategory.DIAGNOSTIC


# ---------------------------------------------------------------------------
# TwinguardAlarmTracker._parse_surveillance_events (unit-level)
# ---------------------------------------------------------------------------


def test_parse_surveillance_events_list() -> None:
    """_parse_surveillance_events handles a native list."""
    result = TwinguardAlarmTracker._parse_surveillance_events(
        [{"triggerId": "tg-1", "type": "ALARM_ON"}, "bad-entry"]
    )
    assert result == [{"triggerId": "tg-1", "type": "ALARM_ON"}]


def test_parse_surveillance_events_json_string() -> None:
    """_parse_surveillance_events handles a JSON-encoded string."""
    payload = json.dumps([{"triggerId": "tg-2"}, {"triggerId": "tg-3"}])
    result = TwinguardAlarmTracker._parse_surveillance_events(payload)
    assert len(result) == 2
    assert result[0]["triggerId"] == "tg-2"


def test_parse_surveillance_events_empty() -> None:
    """_parse_surveillance_events handles None/empty gracefully."""
    assert TwinguardAlarmTracker._parse_surveillance_events(None) == []
    assert TwinguardAlarmTracker._parse_surveillance_events("") == []


def test_parse_surveillance_events_invalid_json() -> None:
    """_parse_surveillance_events handles malformed JSON gracefully."""
    assert TwinguardAlarmTracker._parse_surveillance_events("not json {{{") == []


def test_parse_surveillance_events_non_list_json() -> None:
    """_parse_surveillance_events returns empty list when JSON is not a list."""
    assert (
        TwinguardAlarmTracker._parse_surveillance_events(json.dumps({"key": "val"}))
        == []
    )
