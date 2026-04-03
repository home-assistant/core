"""Test ONVIF event handling end-to-end."""

from onvif_parsers.model import EventEntity

from homeassistant.components.onvif.models import Capabilities, Event
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MAC, setup_onvif_integration

MOTION_ALARM_UID = f"{MAC}_tns1:VideoSource/MotionAlarm_VideoSourceToken"
IMAGE_TOO_BLURRY_UID = (
    f"{MAC}_tns1:VideoSource/ImageTooBlurry/AnalyticsService_VideoSourceToken"
)
LAST_RESET_UID = f"{MAC}_tns1:Monitoring/LastReset_0"


async def test_motion_alarm_event(hass: HomeAssistant) -> None:
    """Test that a motion alarm event creates a binary sensor."""
    await setup_onvif_integration(
        hass,
        capabilities=Capabilities(events=True, imaging=True, ptz=True),
        events=[
            Event(
                uid=MOTION_ALARM_UID,
                name="Motion Alarm",
                platform="binary_sensor",
                device_class="motion",
                value=True,
            ),
        ],
    )

    state = hass.states.get("binary_sensor.testcamera_motion_alarm")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes[ATTR_DEVICE_CLASS] == "motion"


async def test_motion_alarm_event_off(hass: HomeAssistant) -> None:
    """Test that a motion alarm event with false value is off."""
    await setup_onvif_integration(
        hass,
        capabilities=Capabilities(events=True, imaging=True, ptz=True),
        events=[
            Event(
                uid=MOTION_ALARM_UID,
                name="Motion Alarm",
                platform="binary_sensor",
                device_class="motion",
                value=False,
            ),
        ],
    )

    state = hass.states.get("binary_sensor.testcamera_motion_alarm")
    assert state is not None
    assert state.state == STATE_OFF


async def test_diagnostic_event_entity_category(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that a diagnostic event gets the correct entity category."""
    await setup_onvif_integration(
        hass,
        capabilities=Capabilities(events=True, imaging=True, ptz=True),
        events=[
            Event(
                uid=IMAGE_TOO_BLURRY_UID,
                name="Image Too Blurry",
                platform="binary_sensor",
                device_class="problem",
                value=True,
                entity_category=EntityCategory.DIAGNOSTIC,
            ),
        ],
    )

    state = hass.states.get("binary_sensor.testcamera_image_too_blurry")
    assert state is not None
    assert state.state == STATE_ON

    entry = entity_registry.async_get("binary_sensor.testcamera_image_too_blurry")
    assert entry is not None
    assert entry.entity_category is EntityCategory.DIAGNOSTIC


async def test_timestamp_event_conversion(hass: HomeAssistant) -> None:
    """Test that timestamp sensor events get string values converted to datetime."""
    await setup_onvif_integration(
        hass,
        capabilities=Capabilities(events=True, imaging=True, ptz=True),
        raw_events=[
            (
                "tns1:Monitoring/LastReset",
                [
                    EventEntity(
                        uid=LAST_RESET_UID,
                        name="Last Reset",
                        platform="sensor",
                        device_class="timestamp",
                        value="2023-10-01T12:00:00Z",
                    ),
                ],
            ),
        ],
    )

    state = hass.states.get("sensor.testcamera_last_reset")
    assert state is not None
    # Verify the string was converted to a datetime (raw string would end
    # with "Z", converted datetime rendered by SensorEntity has "+00:00")
    assert state.state == "2023-10-01T12:00:00+00:00"


async def test_timestamp_event_invalid_value(hass: HomeAssistant) -> None:
    """Test that invalid timestamp values result in unknown state."""
    await setup_onvif_integration(
        hass,
        capabilities=Capabilities(events=True, imaging=True, ptz=True),
        raw_events=[
            (
                "tns1:Monitoring/LastReset",
                [
                    EventEntity(
                        uid=LAST_RESET_UID,
                        name="Last Reset",
                        platform="sensor",
                        device_class="timestamp",
                        value="0000-00-00T00:00:00Z",
                    ),
                ],
            ),
        ],
    )

    state = hass.states.get("sensor.testcamera_last_reset")
    assert state is not None
    assert state.state == "unknown"


async def test_multiple_events_same_topic(hass: HomeAssistant) -> None:
    """Test that multiple events with the same topic are all processed."""
    await setup_onvif_integration(
        hass,
        capabilities=Capabilities(events=True, imaging=True, ptz=True),
        raw_events=[
            (
                "tns1:VideoSource/MotionAlarm",
                [
                    EventEntity(
                        uid=f"{MOTION_ALARM_UID}_1",
                        name="Motion Alarm 1",
                        platform="binary_sensor",
                        device_class="motion",
                        value=True,
                    ),
                    EventEntity(
                        uid=f"{MOTION_ALARM_UID}_2",
                        name="Motion Alarm 2",
                        platform="binary_sensor",
                        device_class="motion",
                        value=False,
                    ),
                ],
            ),
        ],
    )

    state1 = hass.states.get("binary_sensor.testcamera_motion_alarm_1")
    assert state1 is not None
    assert state1.state == STATE_ON

    state2 = hass.states.get("binary_sensor.testcamera_motion_alarm_2")
    assert state2 is not None
    assert state2.state == STATE_OFF
