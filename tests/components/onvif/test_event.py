"""Test ONVIF event entities."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from onvif_parsers.model import EventEntity
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_capture_events

from homeassistant.components.event import (
    ATTR_EVENT_TYPE,
    ATTR_EVENT_TYPES,
    DOMAIN as EVENT_DOMAIN,
)
from homeassistant.components.onvif.const import CONF_SNAPSHOT_AUTH, DOMAIN
from homeassistant.components.onvif.models import Capabilities
from homeassistant.const import (
    ATTR_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    EVENT_STATE_CHANGED,
    HTTP_DIGEST_AUTHENTICATION,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import (
    HOST,
    MAC,
    NAME,
    PASSWORD,
    PORT,
    USERNAME,
    async_parse_raw_events,
    setup_onvif_integration,
)

LINE_CROSSED_TOPIC = "tns1:RuleEngine/LineDetector/Crossed"
LINE_CROSSED_UID = f"{MAC}_{LINE_CROSSED_TOPIC}_VideoSourceToken_MyLine"
LINE_CROSSED_ENTITY_ID = "event.testcamera_line_detector_crossed"
MOTION_ALARM_TOPIC = "tns1:VideoSource/MotionAlarm"
CAPABILITIES = Capabilities(events=True, imaging=True, ptz=True)

LINE_CROSSED_EVENTS = [
    (
        LINE_CROSSED_TOPIC,
        [
            EventEntity(
                uid=LINE_CROSSED_UID,
                name="Line Detector Crossed",
                platform="event",
                device_class="motion",
            )
        ],
    )
]
MOTION_ALARM_EVENTS = [
    (
        MOTION_ALARM_TOPIC,
        [
            EventEntity(
                uid=f"{MAC}_{MOTION_ALARM_TOPIC}_VideoSourceToken",
                name="Motion Alarm",
                platform="binary_sensor",
                device_class="motion",
                value=True,
            )
        ],
    )
]


@pytest.mark.usefixtures("freezer")
async def test_event_triggered(hass: HomeAssistant) -> None:
    """Test that an event message creates and triggers an event entity."""
    await setup_onvif_integration(
        hass, capabilities=CAPABILITIES, raw_events=LINE_CROSSED_EVENTS
    )

    state = hass.states.get(LINE_CROSSED_ENTITY_ID)
    assert state is not None
    assert state.state == dt_util.utcnow().isoformat(timespec="milliseconds")
    assert state.attributes[ATTR_EVENT_TYPE] == "triggered"
    assert state.attributes[ATTR_EVENT_TYPES] == ["triggered"]
    assert state.attributes[ATTR_DEVICE_CLASS] == "motion"


async def test_event_initialized_not_triggered(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test that "Initialized" messages create the entity without triggering it."""
    _, _, mock_device = await setup_onvif_integration(
        hass,
        capabilities=CAPABILITIES,
        raw_events=LINE_CROSSED_EVENTS,
        property_operation="Initialized",
    )

    state = hass.states.get(LINE_CROSSED_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_UNKNOWN

    freezer.tick(timedelta(seconds=10))
    event_manager = mock_device.events
    await async_parse_raw_events(event_manager, LINE_CROSSED_EVENTS)
    event_manager.async_callback_listeners()
    await hass.async_block_till_done()

    triggered_at = dt_util.utcnow().isoformat(timespec="milliseconds")
    assert hass.states.get(LINE_CROSSED_ENTITY_ID).state == triggered_at

    # Renewing the subscription resends "Initialized"
    freezer.tick(timedelta(seconds=10))
    await async_parse_raw_events(
        event_manager, LINE_CROSSED_EVENTS, property_operation="Initialized"
    )
    event_manager.async_callback_listeners()
    await hass.async_block_till_done()

    assert hass.states.get(LINE_CROSSED_ENTITY_ID).state == triggered_at


@pytest.mark.parametrize(
    "property_operation",
    [
        pytest.param(None, id="no_property_operation"),
        pytest.param("Changed", id="changed"),
    ],
)
async def test_event_triggered_on_each_message(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    property_operation: str | None,
) -> None:
    """Test that every message for the event triggers the entity."""
    _, _, mock_device = await setup_onvif_integration(
        hass, capabilities=CAPABILITIES, raw_events=LINE_CROSSED_EVENTS
    )
    event_manager = mock_device.events

    freezer.tick(timedelta(seconds=10))
    await async_parse_raw_events(
        event_manager, LINE_CROSSED_EVENTS, property_operation=property_operation
    )
    event_manager.async_callback_listeners()
    await hass.async_block_till_done()

    triggered_at = dt_util.utcnow().isoformat(timespec="milliseconds")
    assert hass.states.get(LINE_CROSSED_ENTITY_ID).state == triggered_at

    # Messages for other topics must not trigger the entity
    freezer.tick(timedelta(seconds=10))
    await async_parse_raw_events(event_manager, MOTION_ALARM_EVENTS)
    event_manager.async_callback_listeners()
    await hass.async_block_till_done()

    assert hass.states.get(LINE_CROSSED_ENTITY_ID).state == triggered_at


async def test_event_triggered_for_each_message_in_batch(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test that each message for the same event in one batch triggers it."""
    _, _, mock_device = await setup_onvif_integration(
        hass, capabilities=CAPABILITIES, raw_events=LINE_CROSSED_EVENTS
    )
    event_manager = mock_device.events
    state_changes = async_capture_events(hass, EVENT_STATE_CHANGED)

    freezer.tick(timedelta(seconds=10))
    await async_parse_raw_events(event_manager, LINE_CROSSED_EVENTS * 3)
    event_manager.async_callback_listeners()
    await hass.async_block_till_done()

    assert [
        event.data["new_state"].state
        for event in state_changes
        if event.data["entity_id"] == LINE_CROSSED_ENTITY_ID
    ] == [
        (dt_util.utcnow() + timedelta(milliseconds=offset)).isoformat(
            timespec="milliseconds"
        )
        for offset in range(3)
    ]


@pytest.mark.usefixtures("freezer")
async def test_event_created_after_setup(hass: HomeAssistant) -> None:
    """Test that an event entity is created and triggered by its first message."""
    _, _, mock_device = await setup_onvif_integration(
        hass, capabilities=CAPABILITIES, raw_events=MOTION_ALARM_EVENTS
    )
    assert hass.states.get(LINE_CROSSED_ENTITY_ID) is None

    event_manager = mock_device.events
    await async_parse_raw_events(event_manager, LINE_CROSSED_EVENTS)
    event_manager.async_callback_listeners()
    await hass.async_block_till_done()

    state = hass.states.get(LINE_CROSSED_ENTITY_ID)
    assert state is not None
    assert state.state == dt_util.utcnow().isoformat(timespec="milliseconds")


@pytest.mark.usefixtures("freezer")
async def test_event_restored_from_registry(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Test that a known event entity is created before any message arrives."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: NAME,
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_SNAPSHOT_AUTH: HTTP_DIGEST_AUTHENTICATION,
        },
        unique_id=MAC,
    )
    config_entry.add_to_hass(hass)
    entity_id = entity_registry.async_get_or_create(
        EVENT_DOMAIN,
        DOMAIN,
        LINE_CROSSED_UID,
        config_entry=config_entry,
        original_device_class="motion",
        original_name="TestCamera Line Detector Crossed",
    ).entity_id

    _, _, mock_device = await setup_onvif_integration(
        hass,
        capabilities=CAPABILITIES,
        raw_events=MOTION_ALARM_EVENTS,
        config_entry=config_entry,
    )

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNKNOWN
    assert state.attributes[ATTR_DEVICE_CLASS] == "motion"

    event_manager = mock_device.events
    await async_parse_raw_events(event_manager, LINE_CROSSED_EVENTS)
    event_manager.async_callback_listeners()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == dt_util.utcnow().isoformat(
        timespec="milliseconds"
    )
