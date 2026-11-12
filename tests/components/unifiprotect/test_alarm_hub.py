"""Tests for the UniFi Protect Alarm Hub (Public API) entities."""

from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest
from pytest_homeassistant.common import load_json_object_fixture
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from uiprotect import EventChange, ProtectEvent, ProtectEventChannel
from uiprotect.data import DeviceState, EventType, LinkStation, WSAction
from uiprotect.data.public_event import PublicEventMetadata
from uiprotect.websocket import WebsocketState

from homeassistant.components.unifiprotect.const import (
    ATTR_EVENT_ID,
    ATTR_INPUT,
    ATTR_STATUS,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import Event as HAEvent, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from .utils import (
    MockUFPFixture,
    init_entry,
    make_public_bootstrap,
    public_device_ws_message,
)

DOMAIN = "unifiprotect"

ALARM_HUB_MAC = "AABBCCDDEEFF"
HUB_EVENT = "event.alarm_hub"
INPUT_EVENT = "event.alarm_hub_input_7"
NAMED_INPUT_EVENT = "event.alarm_hub_hallway"


def _make_alarm_hub() -> LinkStation:
    """Build a real LinkStation alarm hub from the sample fixture."""
    data = load_json_object_fixture("sample_alarm_hub.json", DOMAIN)
    return LinkStation.from_unifi_dict(**data)


def _make_public_bootstrap(hub: LinkStation | None) -> Mock:
    """Build a public bootstrap mock holding the given alarm hub."""
    nvr = Mock()
    # Distinct from ALARM_HUB_MAC: a shared mac would make the hub its own via device.
    nvr.mac = "112233445566"
    nvr.name = "Test NVR"
    nvr.display_name = "Test NVR"
    nvr.device_type = None
    nvr.type = None
    nvr.unifi_dict.return_value = {"name": "Test NVR"}
    hubs = {hub.id: hub} if hub is not None else {}
    # Alarm hubs are the alarm-hub subset of the link stations.
    return make_public_bootstrap(alarm_hubs=hubs, link_stations=dict(hubs), nvr=nvr)


@pytest.fixture(name="alarm_hub")
def _alarm_hub_fixture() -> LinkStation:
    return _make_alarm_hub()


def _hub_event(
    hub: LinkStation,
    event_type: EventType,
    metadata: PublicEventMetadata | None,
    event_id: str = "evt-1",
) -> ProtectEvent:
    """Build an alarm hub ``ProtectEvent``; real ones have ``start == end``."""
    when = datetime(2026, 1, 1)
    return ProtectEvent(
        id=event_id,
        type=event_type,
        channel=ProtectEventChannel.ALARM_HUB,
        device_id=hub.id,
        device_mac=hub.mac,
        start=when,
        end=when,
        metadata=metadata,
    )


@pytest.fixture(name="ufp_with_alarm_hub")
def _ufp_with_alarm_hub(ufp: MockUFPFixture, alarm_hub: LinkStation) -> MockUFPFixture:
    """Configure the ufp fixture with one alarm hub via the public API."""
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(alarm_hub)
    return ufp


async def test_event_not_created_without_public_bootstrap(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """No alarm hub entity when the public bootstrap is unavailable."""
    ufp.api.has_public_bootstrap = False
    await init_entry(hass, ufp, [])
    assert hass.states.get(HUB_EVENT) is None


async def test_alarm_hub_in_diagnostics(
    hass: HomeAssistant,
    ufp_with_alarm_hub: MockUFPFixture,
    hass_client: ClientSessionGenerator,
) -> None:
    """Alarm hubs are included (anonymized) in config entry diagnostics."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    diag = await get_diagnostics_for_config_entry(
        hass, hass_client, ufp_with_alarm_hub.entry
    )

    hubs = diag["public_bootstrap"]["link_stations"]
    assert len(hubs) == 1
    hub = hubs[0]
    # Anonymized: the real MAC must not leak.
    assert hub["mac"] != ALARM_HUB_MAC
    assert "alarmHub" in hub


async def test_alarm_hub_device_and_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    ufp_with_alarm_hub: MockUFPFixture,
    snapshot: SnapshotAssertion,
) -> None:
    """Snapshot the alarm hub device and all of its entities."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, ALARM_HUB_MAC), ufp_with_alarm_hub.entry.entry_id
    )
    assert device is not None
    assert device == snapshot(name="device")

    entries = er.async_entries_for_device(
        entity_registry, device.id, include_disabled_entities=True
    )
    assert entries
    for entry in sorted(entries, key=lambda e: e.entity_id):
        assert entry == snapshot(name=entry.entity_id)
        assert hass.states.get(entry.entity_id) == snapshot(
            name=f"{entry.entity_id}-state"
        )


async def test_alarm_hub_availability_follows_public_ws(
    hass: HomeAssistant,
    ufp_with_alarm_hub: MockUFPFixture,
) -> None:
    """Availability tracks the public websocket health, not the private one."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    entity_id = HUB_EVENT
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    # Private connection drops: the public-only alarm hub stays available.
    assert ufp_with_alarm_hub.ws_state_subscription is not None
    ufp_with_alarm_hub.ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    # Public connection drops: now the alarm hub is unavailable.
    assert ufp_with_alarm_hub.devices_ws_state_subscription is not None
    ufp_with_alarm_hub.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # Public connection restored while the private one is still down: available.
    ufp_with_alarm_hub.devices_ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE


async def test_alarm_hub_unavailable_while_disconnected(
    hass: HomeAssistant,
    ufp_with_alarm_hub: MockUFPFixture,
    alarm_hub: LinkStation,
) -> None:
    """A disconnected hub takes all of its entities offline until it is back."""
    await init_entry(hass, ufp_with_alarm_hub, [])
    assert ufp_with_alarm_hub.devices_ws_subscription is not None

    alarm_hub.state = DeviceState.DISCONNECTED
    ufp_with_alarm_hub.devices_ws_subscription(public_device_ws_message(alarm_hub))
    await hass.async_block_till_done()
    assert hass.states.get(HUB_EVENT).state == STATE_UNAVAILABLE

    alarm_hub.state = DeviceState.CONNECTED
    ufp_with_alarm_hub.devices_ws_subscription(public_device_ws_message(alarm_hub))
    await hass.async_block_till_done()
    assert hass.states.get(HUB_EVENT).state != STATE_UNAVAILABLE


async def test_alarm_hub_becomes_unavailable_when_removed(
    hass: HomeAssistant,
    ufp_with_alarm_hub: MockUFPFixture,
    alarm_hub: LinkStation,
) -> None:
    """A delete WS frame (new_obj=None) marks the hub's entities unavailable."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    entity_id = HUB_EVENT
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    # Drop the hub from the public bootstrap, then send a delete frame.
    ufp_with_alarm_hub.api.public_bootstrap.alarm_hubs = {}

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.old_obj = alarm_hub
    mock_msg.new_obj = None
    assert ufp_with_alarm_hub.devices_ws_subscription is not None
    ufp_with_alarm_hub.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    "is_public_only",
    [pytest.param(False, id="hybrid"), pytest.param(True, id="api_key_only")],
)
async def test_alarm_hub_added_at_runtime(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp: MockUFPFixture,
    alarm_hub: LinkStation,
    is_public_only: bool,
) -> None:
    """A hub adopted after setup is discovered from its public add frame."""
    ufp.api.is_public_only = is_public_only
    ufp.api.has_public_bootstrap = True
    pb = _make_public_bootstrap(None)
    ufp.api.public_bootstrap = pb
    ufp.api.update_public = AsyncMock(return_value=pb)

    await init_entry(hass, ufp, [])
    assert hass.states.get(HUB_EVENT) is None

    pb.alarm_hubs = {alarm_hub.id: alarm_hub}
    msg = public_device_ws_message(alarm_hub)
    msg.action = WSAction.ADD
    assert ufp.devices_ws_subscription is not None
    ufp.devices_ws_subscription(msg)
    await hass.async_block_till_done()

    assert hass.states.get(HUB_EVENT) is not None
    assert (
        entity_registry.async_get(HUB_EVENT).unique_id == f"{ALARM_HUB_MAC}_alarm_hub"
    )


async def test_alarm_hub_known_at_setup_not_added_again(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    ufp_with_alarm_hub: MockUFPFixture,
    alarm_hub: LinkStation,
) -> None:
    """An add frame for a hub that existed at setup does not add it twice."""
    await init_entry(hass, ufp_with_alarm_hub, [])
    entity_ids = hass.states.async_entity_ids()

    msg = public_device_ws_message(alarm_hub)
    msg.action = WSAction.ADD
    assert ufp_with_alarm_hub.devices_ws_subscription is not None
    ufp_with_alarm_hub.devices_ws_subscription(msg)
    await hass.async_block_till_done()

    assert hass.states.async_entity_ids() == entity_ids
    assert "does not generate unique IDs" not in caplog.text


@pytest.mark.parametrize(
    "is_public_only",
    [pytest.param(False, id="hybrid"), pytest.param(True, id="api_key_only")],
)
async def test_plain_link_station_added_at_runtime(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    ufp: MockUFPFixture,
    alarm_hub: LinkStation,
    is_public_only: bool,
) -> None:
    """A link station that is not an alarm hub gets no alarm hub entities."""
    link_station = alarm_hub.model_copy(update={"is_alarm_hub": False})
    ufp.api.is_public_only = is_public_only
    ufp.api.has_public_bootstrap = True
    pb = _make_public_bootstrap(None)
    ufp.api.public_bootstrap = pb
    ufp.api.update_public = AsyncMock(return_value=pb)

    await init_entry(hass, ufp, [])
    msg = public_device_ws_message(link_station)
    msg.action = WSAction.ADD
    assert ufp.devices_ws_subscription is not None
    ufp.devices_ws_subscription(msg)
    await hass.async_block_till_done()

    assert (
        device_registry.async_get_device_by_connection(
            (dr.CONNECTION_NETWORK_MAC, ALARM_HUB_MAC), ufp.entry.entry_id
        )
        is None
    )
    assert hass.states.get(HUB_EVENT) is None


@pytest.mark.parametrize(
    ("device_type", "model", "object_id"),
    [
        pytest.param(None, "Alarm Hub", "alarm_hub", id="no_type"),
        pytest.param("UP-Hub-Test", "UP-Hub-Test", "up_hub_test", id="type"),
    ],
)
async def test_alarm_hub_without_name(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    ufp: MockUFPFixture,
    alarm_hub: LinkStation,
    device_type: str | None,
    model: str,
    object_id: str,
) -> None:
    """A hub without a name falls back to its model and MAC."""
    unnamed = alarm_hub.model_copy(update={"name": None, "device_type": device_type})
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(unnamed)

    await init_entry(hass, ufp, [])

    device = device_registry.async_get_device_by_connection(
        (dr.CONNECTION_NETWORK_MAC, ALARM_HUB_MAC), ufp.entry.entry_id
    )
    assert device is not None
    assert device.name == f"{model} {ALARM_HUB_MAC}"
    assert device.model == model
    assert device.model_id == device_type
    assert hass.states.get(f"event.{object_id}_{ALARM_HUB_MAC.lower()}") is not None


async def test_alarm_hub_unavailable_when_public_bootstrap_lost(
    hass: HomeAssistant,
    ufp_with_alarm_hub: MockUFPFixture,
    alarm_hub: LinkStation,
) -> None:
    """Losing the public bootstrap marks alarm hub entities unavailable."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    entity_id = HUB_EVENT
    assert hass.states.get(entity_id).state != STATE_UNAVAILABLE

    ufp_with_alarm_hub.api.has_public_bootstrap = False
    # A frame without a merged object makes the entities re-read the bootstrap.
    msg = public_device_ws_message(None)
    msg.old_obj = alarm_hub
    assert ufp_with_alarm_hub.devices_ws_subscription is not None
    ufp_with_alarm_hub.devices_ws_subscription(msg)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


def _capture_events(hass: HomeAssistant, *entity_ids: str) -> list[HAEvent]:
    """Collect the state changes of the given entities."""
    events: list[HAEvent] = []

    @callback
    def _capture(event: HAEvent) -> None:
        events.append(event)

    async_track_state_change_event(hass, entity_ids, _capture)
    return events


@pytest.mark.parametrize(
    ("event_type", "status", "expected_type"),
    [
        pytest.param(EventType.ALARM_HUB_MOTION, "alarm", "motion", id="motion"),
        pytest.param(
            EventType.ALARM_HUB_ENTRY_OPENED, "alarm", "entry_opened", id="entry_opened"
        ),
        pytest.param(
            EventType.ALARM_HUB_ENTRY_CLOSED,
            "normal",
            "entry_closed",
            id="entry_closed",
        ),
        pytest.param(EventType.ALARM_HUB_SMOKE, "alarm", "smoke", id="smoke"),
        pytest.param(
            EventType.ALARM_HUB_GLASS_BREAK, "alarm", "glass_break", id="glass_break"
        ),
        pytest.param(
            EventType.ALARM_HUB_BUTTON_PRESS, "alarm", "button_press", id="button_press"
        ),
        pytest.param(EventType.ALARM_HUB_TAMPER, "tamper", "tamper", id="tamper"),
    ],
)
async def test_alarm_hub_input_event_fires(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp_with_alarm_hub: MockUFPFixture,
    alarm_hub: LinkStation,
    event_type: EventType,
    status: str,
    expected_type: str,
) -> None:
    """An input event fires on the entity of that input only."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    # Input 6 of the API is input 7 in Protect.
    entity = entity_registry.async_get(INPUT_EVENT)
    assert entity is not None
    assert entity.unique_id == f"{ALARM_HUB_MAC}_input_6"

    events = _capture_events(hass, INPUT_EVENT, HUB_EVENT, NAMED_INPUT_EVENT)
    metadata = PublicEventMetadata(pin="6", status_text=status)
    # Protect dispatches every change of an event; it must fire only once.
    for change in (EventChange.STARTED, EventChange.ENDED):
        ufp_with_alarm_hub.events_msg(
            _hub_event(alarm_hub, event_type, metadata), change
        )
        await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["entity_id"] == INPUT_EVENT
    attributes = events[0].data["new_state"].attributes
    assert attributes["event_type"] == expected_type
    assert attributes[ATTR_EVENT_ID] == "evt-1"
    assert attributes[ATTR_STATUS] == status
    assert ATTR_INPUT not in attributes


async def test_alarm_hub_named_input_event(
    hass: HomeAssistant,
    ufp_with_alarm_hub: MockUFPFixture,
    alarm_hub: LinkStation,
) -> None:
    """An input named in Protect uses that name for its entity."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    events = _capture_events(hass, INPUT_EVENT, HUB_EVENT, NAMED_INPUT_EVENT)
    metadata = PublicEventMetadata(pin="24", status_text="alarm")
    ufp_with_alarm_hub.events_msg(
        _hub_event(alarm_hub, EventType.ALARM_HUB_MOTION, metadata),
        EventChange.STARTED,
    )
    await hass.async_block_till_done()

    assert [event.data["entity_id"] for event in events] == [NAMED_INPUT_EVENT]


@pytest.mark.parametrize(
    ("event_type", "metadata", "expected_type", "expected_status"),
    [
        pytest.param(
            EventType.ALARM_HUB_DEVICE_TAMPER,
            PublicEventMetadata(status_text="tampered"),
            "device_tamper",
            "tampered",
            id="device_tamper",
        ),
        pytest.param(
            EventType.ALARM_HUB_RELAY_SWITCHED,
            None,
            "relay_switched",
            None,
            id="relay_switched",
        ),
        pytest.param(
            EventType.ALARM_HUB_BATTERY_LOW, None, "battery_low", None, id="battery_low"
        ),
        pytest.param(
            EventType.ALARM_HUB_BATTERY_CONNECTED,
            PublicEventMetadata(),
            "battery_connected",
            None,
            id="battery_connected",
        ),
    ],
)
async def test_alarm_hub_event_fires(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp_with_alarm_hub: MockUFPFixture,
    alarm_hub: LinkStation,
    event_type: EventType,
    metadata: PublicEventMetadata | None,
    expected_type: str,
    expected_status: str | None,
) -> None:
    """An event of the hub itself fires on the hub entity."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    entity = entity_registry.async_get(HUB_EVENT)
    assert entity is not None
    assert entity.unique_id == f"{ALARM_HUB_MAC}_alarm_hub"

    events = _capture_events(hass, INPUT_EVENT, HUB_EVENT, NAMED_INPUT_EVENT)
    ufp_with_alarm_hub.events_msg(
        _hub_event(alarm_hub, event_type, metadata), EventChange.STARTED
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["entity_id"] == HUB_EVENT
    attributes = events[0].data["new_state"].attributes
    assert attributes["event_type"] == expected_type
    assert attributes.get(ATTR_STATUS) == expected_status
    assert ATTR_INPUT not in attributes


async def test_alarm_hub_emergency_input_fires_on_hub(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp_with_alarm_hub: MockUFPFixture,
    alarm_hub: LinkStation,
) -> None:
    """The emergency input has no numbered terminal and no entity of its own."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    assert (
        entity_registry.async_get_entity_id(
            "event", DOMAIN, f"{ALARM_HUB_MAC}_input_32"
        )
        is None
    )

    events = _capture_events(hass, HUB_EVENT)
    metadata = PublicEventMetadata(pin="32", status_text="alarm")
    ufp_with_alarm_hub.events_msg(
        _hub_event(alarm_hub, EventType.ALARM_HUB_BUTTON_PRESS, metadata),
        EventChange.STARTED,
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    attributes = events[0].data["new_state"].attributes
    assert attributes["event_type"] == "button_press"
    assert ATTR_INPUT not in attributes


async def test_alarm_hub_disabled_input_fires_on_hub(
    hass: HomeAssistant,
    ufp_with_alarm_hub: MockUFPFixture,
    alarm_hub: LinkStation,
) -> None:
    """A disabled input has no entity; its events name the input on the hub."""
    alarm_hub.alarm_hub["input"]["24"]["enable"] = "off"
    await init_entry(hass, ufp_with_alarm_hub, [])

    assert hass.states.get(NAMED_INPUT_EVENT) is None

    events = _capture_events(hass, HUB_EVENT)
    metadata = PublicEventMetadata(pin="24", status_text="alarm")
    ufp_with_alarm_hub.events_msg(
        _hub_event(alarm_hub, EventType.ALARM_HUB_MOTION, metadata),
        EventChange.STARTED,
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    attributes = events[0].data["new_state"].attributes
    assert attributes["event_type"] == "motion"
    assert attributes[ATTR_INPUT] == 25


async def test_alarm_hub_inputs_without_terminal_list(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp_with_alarm_hub: MockUFPFixture,
    alarm_hub: LinkStation,
) -> None:
    """Without a terminal list every enabled input gets an entity."""
    del alarm_hub.alarm_hub["connector"]
    await init_entry(hass, ufp_with_alarm_hub, [])

    assert (
        entity_registry.async_get_entity_id(
            "event", DOMAIN, f"{ALARM_HUB_MAC}_input_32"
        )
        is not None
    )


async def test_alarm_hub_event_covers_all_hub_event_types(
    hass: HomeAssistant,
    ufp_with_alarm_hub: MockUFPFixture,
) -> None:
    """The hub entity declares one type per alarm hub event of the library."""
    await init_entry(hass, ufp_with_alarm_hub, [])

    hub_event_types = [
        event_type
        for event_type in EventType
        if event_type.name.startswith("ALARM_HUB_")
    ]
    assert len(hass.states.get(HUB_EVENT).attributes["event_types"]) == len(
        hub_event_types
    )


async def test_alarm_hub_event_unavailable_on_events_ws_disconnect(
    hass: HomeAssistant,
    ufp_with_alarm_hub: MockUFPFixture,
) -> None:
    """The event entity follows the events websocket it is fed from."""
    await init_entry(hass, ufp_with_alarm_hub, [])
    assert hass.states.get(HUB_EVENT).state != STATE_UNAVAILABLE

    assert ufp_with_alarm_hub.events_ws_state_subscription is not None
    ufp_with_alarm_hub.events_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()
    assert hass.states.get(HUB_EVENT).state == STATE_UNAVAILABLE

    ufp_with_alarm_hub.events_ws_state_subscription(WebsocketState.CONNECTED)
    await hass.async_block_till_done()
    assert hass.states.get(HUB_EVENT).state != STATE_UNAVAILABLE
