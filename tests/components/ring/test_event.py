"""The tests for the Ring event platform."""

from datetime import datetime
import time
from unittest.mock import Mock

from freezegun.api import FrozenDateTimeFactory
import pytest
from ring_doorbell import Ring
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ring.binary_sensor import RingEvent
from homeassistant.components.ring.coordinator import RingEventListener
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .common import MockConfigEntry, setup_platform
from .device_mocks import FRONT_DOOR_DEVICE_ID, INGRESS_DEVICE_ID

from tests.common import snapshot_platform


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
    ("device_id", "device_name", "alert_kind", "device_class"),
    [
        pytest.param(
            FRONT_DOOR_DEVICE_ID,
            "front_door",
            "motion",
            "motion",
            id="front_door_motion",
        ),
        pytest.param(
            FRONT_DOOR_DEVICE_ID, "front_door", "ding", "doorbell", id="front_door_ding"
        ),
        pytest.param(
            INGRESS_DEVICE_ID, "ingress", "ding", "doorbell", id="ingress_ding"
        ),
        pytest.param(
            INGRESS_DEVICE_ID,
            "ingress",
            "intercom_unlock",
            "button",
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
) -> None:
    """Test the Ring event platforms."""

    await setup_platform(hass, Platform.EVENT)

    start_time_str = "2024-09-04T15:32:53.892+00:00"
    start_time = datetime.strptime(start_time_str, "%Y-%m-%dT%H:%M:%S.%f%z")
    freezer.move_to(start_time)
    on_event_cb = mock_ring_event_listener_class.return_value.add_notification_callback.call_args.args[
        0
    ]

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
