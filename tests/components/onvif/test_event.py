"""Test ONVIF event handling end-to-end."""

from homeassistant.components.onvif.models import Capabilities, Event
from homeassistant.const import ATTR_DEVICE_CLASS, STATE_OFF, STATE_ON, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MAC, setup_onvif_integration

MOTION_ALARM_UID = f"{MAC}_tns1:VideoSource/MotionAlarm_VideoSourceToken"
IMAGE_TOO_BLURRY_UID = (
    f"{MAC}_tns1:VideoSource/ImageTooBlurry/AnalyticsService_VideoSourceToken"
)


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
