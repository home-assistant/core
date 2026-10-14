"""The tests for the Ring event platform."""

from datetime import datetime, timedelta
import time
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest
from ring_doorbell import Ring
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.event import ATTR_EVENT_TYPE, DoorbellEventType
from homeassistant.components.ring.binary_sensor import RingEvent
from homeassistant.components.ring.const import DOMAIN
from homeassistant.components.ring.coordinator import (
    LISTENER_CHECK_INTERVAL,
    LISTENER_ISSUE_ID,
    LISTENER_MAX_RESTART_DELAY,
    LISTENER_RESTART_ISSUE_THRESHOLD,
    RingEventListener,
)
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er, issue_registry as ir

from .common import MockConfigEntry, setup_platform
from .device_mocks import FRONT_DOOR_DEVICE_ID, INGRESS_DEVICE_ID

from tests.common import async_fire_time_changed, snapshot_platform


async def test_states(
    hass: HomeAssistant,
    mock_ring_client: Mock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test states."""
    mock_config_entry.add_to_hass(hass)
    await setup_platform(hass, Platform.EVENT)
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    ("device_id", "device_name", "alert_kind", "device_class", "event_type"),
    [
        pytest.param(
            FRONT_DOOR_DEVICE_ID,
            "front_door",
            "motion",
            "motion",
            "motion",
            id="front_door_motion",
        ),
        pytest.param(
            FRONT_DOOR_DEVICE_ID,
            "front_door",
            "ding",
            "doorbell",
            DoorbellEventType.RING,
            id="front_door_ding",
        ),
        pytest.param(
            INGRESS_DEVICE_ID,
            "ingress",
            "ding",
            "doorbell",
            DoorbellEventType.RING,
            id="ingress_ding",
        ),
        pytest.param(
            INGRESS_DEVICE_ID,
            "ingress",
            "intercom_unlock",
            "button",
            "intercom_unlock",
            id="ingress_unlock",
        ),
    ],
)
async def test_event(
    hass: HomeAssistant,
    mock_ring_client: Ring,
    mock_ring_event_listener_class: RingEventListener,
    freezer: FrozenDateTimeFactory,
    device_id: int,
    device_name: str,
    alert_kind: str,
    device_class: str,
    event_type: str,
) -> None:
    """Test the Ring event platforms."""

    await setup_platform(hass, Platform.EVENT)

    start_time_str = "2024-09-04T15:32:53.892+00:00"
    start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S.%f%z")
    freezer.move_to(start_time)
    listener = mock_ring_event_listener_class.return_value
    on_event_cb = listener.add_notification_callback.call_args.args[0]

    # Default state is unknown
    entity_id = f"event.{device_name}_{alert_kind}"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"
    assert state.attributes["device_class"] == device_class

    # A new alert sets to on
    event = RingEvent(
        1234546, device_id, "Foo", "Bar", time.time(), 180, kind=alert_kind, state=None
    )
    mock_ring_client.active_alerts.return_value = [event]
    on_event_cb(event)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == start_time_str
    assert state.attributes[ATTR_EVENT_TYPE] == event_type


ENTITY_ID = "event.front_door_ding"


def _set_restart_result(listener: Mock, started: bool) -> None:
    """Make the next listener start succeed or fail."""

    async def _start(*, timeout: int) -> bool:
        listener.started = started
        return started

    listener.start.side_effect = _start


async def _check_listener(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, delay: timedelta
) -> None:
    """Advance time so the listener check runs."""
    freezer.tick(delay)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_listener_restarted(
    hass: HomeAssistant,
    mock_ring_client: Mock,
    mock_ring_event_listener_class: Mock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a stopped event listener makes entities unavailable and is restarted."""
    await setup_platform(hass, Platform.EVENT)
    listener = mock_ring_event_listener_class.return_value
    assert mock_ring_event_listener_class.call_count == 1

    # A healthy listener is left alone.
    await _check_listener(hass, freezer, LISTENER_CHECK_INTERVAL)
    assert mock_ring_event_listener_class.call_count == 1

    listener.started = False
    _set_restart_result(listener, False)
    await _check_listener(hass, freezer, LISTENER_CHECK_INTERVAL)

    assert mock_ring_event_listener_class.call_count == 2
    listener.stop.assert_called_once()
    assert hass.states.get(ENTITY_ID).state == STATE_UNAVAILABLE

    # Failed restarts back off before trying again.
    await _check_listener(hass, freezer, LISTENER_CHECK_INTERVAL)
    assert mock_ring_event_listener_class.call_count == 2

    _set_restart_result(listener, True)
    await _check_listener(hass, freezer, LISTENER_CHECK_INTERVAL)

    assert mock_ring_event_listener_class.call_count == 3
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN

    # The restarted listener delivers events to the entities.
    event = RingEvent(
        1234546,
        FRONT_DOOR_DEVICE_ID,
        "Foo",
        "Bar",
        time.time(),
        180,
        kind="ding",
        state=None,
    )
    mock_ring_client.active_alerts.return_value = [event]
    on_event_cb = listener.add_notification_callback.call_args.args[0]
    on_event_cb(event)
    assert hass.states.get(ENTITY_ID).state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)


@pytest.mark.usefixtures("mock_ring_client")
async def test_listener_restart_issue(
    hass: HomeAssistant,
    mock_ring_event_listener_class: Mock,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a repair issue is raised while the listener cannot be restarted."""
    await setup_platform(hass, Platform.EVENT)
    listener = mock_ring_event_listener_class.return_value
    listener.started = False
    _set_restart_result(listener, False)

    for _ in range(LISTENER_RESTART_ISSUE_THRESHOLD - 1):
        await _check_listener(hass, freezer, LISTENER_MAX_RESTART_DELAY)
    assert issue_registry.async_get_issue(DOMAIN, LISTENER_ISSUE_ID) is None

    await _check_listener(hass, freezer, LISTENER_MAX_RESTART_DELAY)
    assert issue_registry.async_get_issue(DOMAIN, LISTENER_ISSUE_ID)
    assert (
        mock_ring_event_listener_class.call_count
        == LISTENER_RESTART_ISSUE_THRESHOLD + 1
    )

    _set_restart_result(listener, True)
    await _check_listener(hass, freezer, LISTENER_MAX_RESTART_DELAY)
    assert issue_registry.async_get_issue(DOMAIN, LISTENER_ISSUE_ID) is None
    assert hass.states.get(ENTITY_ID).state == STATE_UNKNOWN


@pytest.mark.usefixtures("mock_ring_client")
async def test_listener_check_stops_on_unload(
    hass: HomeAssistant,
    mock_ring_event_listener_class: Mock,
    freezer: FrozenDateTimeFactory,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test unloading stops checking a listener that already stopped."""
    await setup_platform(hass, Platform.EVENT)
    listener = mock_ring_event_listener_class.return_value
    listener.started = False
    _set_restart_result(listener, False)
    for _ in range(LISTENER_RESTART_ISSUE_THRESHOLD):
        await _check_listener(hass, freezer, LISTENER_MAX_RESTART_DELAY)
    assert issue_registry.async_get_issue(DOMAIN, LISTENER_ISSUE_ID)
    call_count = mock_ring_event_listener_class.call_count

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert await hass.config_entries.async_unload(entry.entry_id)
    await _check_listener(hass, freezer, LISTENER_MAX_RESTART_DELAY)

    assert mock_ring_event_listener_class.call_count == call_count
    assert issue_registry.async_get_issue(DOMAIN, LISTENER_ISSUE_ID) is None
