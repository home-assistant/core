"""Tests for the UniFi Protect key fob (Public API) entities."""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from uiprotect import EventChange, ProtectEvent, ProtectEventChannel
from uiprotect.data import (
    DeviceState,
    EventType,
    Fob,
    FobAwayState,
    FobButton,
    ModelType,
    PublicBootstrap,
    PublicFobFeatureFlags,
)
from uiprotect.data.public_devices import (
    PublicSignalState,
    PublicWirelessBatteryStatus,
    PublicWirelessConnectionState,
)
from uiprotect.data.public_event import PublicEventMetadata
from uiprotect.data.types import EventButtonType
from uiprotect.websocket import WebsocketState

from homeassistant.components.unifiprotect.const import ATTR_EVENT_ID
from homeassistant.const import ATTR_ATTRIBUTION, STATE_UNAVAILABLE
from homeassistant.core import Event as HAEvent, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.event import async_track_state_change_event

from .utils import MockUFPFixture, enable_entity, init_entry

FOB_ID = "fob-id-1"
FOB_MAC = "AA:BB:CC:DD:EE:F0"
FOB_NAME = "Front Door Fob"

BATTERY_SENSOR = "sensor.front_door_fob_battery"
SIGNAL_SENSOR = "sensor.front_door_fob_signal_strength"
STATUS_SENSOR = "sensor.front_door_fob_status"
BATTERY_LOW_BINARY = "binary_sensor.front_door_fob_battery"
BUTTON_EVENT = "event.front_door_fob_button"


def _make_fob(
    *,
    buttons: list[FobButton] | None = None,
    away_state: FobAwayState = FobAwayState.ONLINE,
    percentage: int | None = 80,
    is_low: bool = False,
    signal_strength: int | None = -55,
    state: DeviceState = DeviceState.CONNECTED,
    name: str | None = FOB_NAME,
) -> Mock:
    """Build a mock :class:`Fob` backed by real public sub-models."""
    fob = Mock(spec=Fob)
    fob.id = FOB_ID
    fob.mac = FOB_MAC
    fob.name = name
    fob.model = ModelType.FOB
    fob.state = state
    fob.away_state = away_state
    # Real USL-FOB hardware reports an empty featureFlags.buttons.
    fob.feature_flags = PublicFobFeatureFlags(buttons=buttons or [])
    fob.wireless_connection_state = PublicWirelessConnectionState(
        battery_status=PublicWirelessBatteryStatus(
            percentage=percentage, is_low=is_low
        ),
        signal_state=PublicSignalState(
            signal_strength=signal_strength, signal_quality=None
        ),
    )
    return fob


def _make_public_bootstrap(fob: Mock | None) -> Mock:
    """Build a public bootstrap mock holding the given fob."""
    pb = Mock(spec=PublicBootstrap)
    pb.fobs = {fob.id: fob} if fob is not None else {}
    pb.relays = {}
    pb.sirens = {}
    pb.arm_mode = None
    pb.arm_profiles = {}
    return pb


@pytest.fixture(name="ufp_with_fob")
def _ufp_with_fob(ufp: MockUFPFixture) -> tuple[MockUFPFixture, Mock]:
    """Configure the ufp fixture with a single key fob on the public API."""
    fob = _make_fob()
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(fob)
    return ufp, fob


def _button_event(
    fob: Mock,
    *,
    event_id: str = "evt-1",
    button: EventButtonType = EventButtonType.ARM,
    event_type: EventType = EventType.SENSOR_BUTTON_PRESSED,
    device_id: str | None = None,
    device_mac: str | None = None,
    now: datetime | None = None,
) -> ProtectEvent:
    """Build a button-press ``ProtectEvent`` matching a real USL-FOB capture.

    A real press is born-closed (``start == end``) and carries the fob itself as
    the event ``device`` with the pressed button in ``metadata.button``.
    """
    when = now or datetime(2026, 1, 1)
    return ProtectEvent(
        id=event_id,
        type=event_type,
        channel=ProtectEventChannel.SENSOR,
        device_id=fob.id if device_id is None else device_id,
        device_mac=fob.mac if device_mac is None else device_mac,
        start=when,
        end=when,
        metadata=PublicEventMetadata(button=button),
    )


async def test_fob_not_created_without_public_bootstrap(
    hass: HomeAssistant, ufp: MockUFPFixture
) -> None:
    """No fob entities are created when the public bootstrap is unavailable."""
    ufp.api.has_public_bootstrap = False
    await init_entry(hass, ufp, [])

    assert hass.states.get(BATTERY_SENSOR) is None
    assert hass.states.get(BUTTON_EVENT) is None


async def test_fob_entities_created(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    ufp_with_fob: tuple[MockUFPFixture, Mock],
) -> None:
    """The fob device and its entities are created from the public bootstrap."""
    ufp, _fob = ufp_with_fob
    await init_entry(hass, ufp, [])

    device = device_registry.async_get_device(
        connections={(dr.CONNECTION_NETWORK_MAC, FOB_MAC)}
    )
    assert device is not None
    assert device.name == FOB_NAME

    battery = entity_registry.async_get(BATTERY_SENSOR)
    assert battery is not None
    assert battery.unique_id == f"{FOB_MAC}_battery_level"
    state = hass.states.get(BATTERY_SENSOR)
    assert state is not None
    assert state.state == "80"
    assert state.attributes[ATTR_ATTRIBUTION]

    # Signal strength is a diagnostic sensor, disabled by default.
    assert hass.states.get(SIGNAL_SENSOR) is None
    signal = entity_registry.async_get(SIGNAL_SENSOR)
    assert signal is not None
    assert signal.disabled

    status = hass.states.get(STATUS_SENSOR)
    assert status is not None
    assert status.state == "online"

    battery_low = hass.states.get(BATTERY_LOW_BINARY)
    assert battery_low is not None
    assert battery_low.state == "off"


async def test_fob_button_event_types_are_full_vocabulary(
    hass: HomeAssistant,
    ufp_with_fob: tuple[MockUFPFixture, Mock],
) -> None:
    """The button event entity declares the full FobButton vocabulary.

    Real hardware reports an empty ``feature_flags.buttons``, so the entity
    cannot derive its types from the device and declares them all.
    """
    ufp, _fob = ufp_with_fob
    await init_entry(hass, ufp, [])

    state = hass.states.get(BUTTON_EVENT)
    assert state is not None
    assert set(state.attributes["event_types"]) == {
        "function",
        "alarm_hub_button",
        "arm",
        "disarm",
        "night",
        "panic",
        "left",
        "right",
        "input1",
        "input2",
    }


async def test_fob_button_press_fires_event(
    hass: HomeAssistant,
    ufp_with_fob: tuple[MockUFPFixture, Mock],
) -> None:
    """A sensor button-press event fires the fob button event entity."""
    ufp, fob = ufp_with_fob
    await init_entry(hass, ufp, [])

    events: list[HAEvent] = []

    @callback
    def _capture(event: HAEvent) -> None:
        events.append(event)

    unsub = async_track_state_change_event(hass, BUTTON_EVENT, _capture)

    ufp.events_msg(_button_event(fob, button=EventButtonType.ARM), EventChange.STARTED)
    await hass.async_block_till_done()

    assert len(events) == 1
    new_state = events[0].data["new_state"]
    assert new_state.attributes["event_type"] == "arm"
    assert new_state.attributes[ATTR_EVENT_ID] == "evt-1"
    unsub()


async def test_fob_alarm_hub_button_press_also_fires(
    hass: HomeAssistant,
    ufp_with_fob: tuple[MockUFPFixture, Mock],
) -> None:
    """An ``alarmHubButtonPress`` event also fires (alarm-hub-paired fobs)."""
    ufp, fob = ufp_with_fob
    await init_entry(hass, ufp, [])

    events: list[HAEvent] = []

    @callback
    def _capture(event: HAEvent) -> None:
        events.append(event)

    unsub = async_track_state_change_event(hass, BUTTON_EVENT, _capture)

    ufp.events_msg(
        _button_event(
            fob,
            button=EventButtonType.PANIC,
            event_type=EventType.ALARM_HUB_BUTTON_PRESS,
        ),
        EventChange.STARTED,
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["new_state"].attributes["event_type"] == "panic"
    unsub()


async def test_fob_unknown_button_is_skipped(
    hass: HomeAssistant,
    ufp_with_fob: tuple[MockUFPFixture, Mock],
) -> None:
    """A press for an unrecognized button (coerced to UNKNOWN) does not fire."""
    ufp, fob = ufp_with_fob
    await init_entry(hass, ufp, [])

    events: list[HAEvent] = []

    @callback
    def _capture(event: HAEvent) -> None:
        events.append(event)

    unsub = async_track_state_change_event(hass, BUTTON_EVENT, _capture)

    ufp.events_msg(
        _button_event(fob, button=EventButtonType.UNKNOWN), EventChange.STARTED
    )
    await hass.async_block_till_done()

    assert len(events) == 0
    unsub()


async def test_fob_alarm_hub_button_uses_snake_case_event_type(
    hass: HomeAssistant,
    ufp_with_fob: tuple[MockUFPFixture, Mock],
) -> None:
    """The camelCase ``alarmHubButton`` wire value maps to a snake_case type."""
    ufp, fob = ufp_with_fob
    await init_entry(hass, ufp, [])

    state = hass.states.get(BUTTON_EVENT)
    assert state is not None
    assert "alarm_hub_button" in state.attributes["event_types"]

    events: list[HAEvent] = []

    @callback
    def _capture(event: HAEvent) -> None:
        events.append(event)

    unsub = async_track_state_change_event(hass, BUTTON_EVENT, _capture)

    ufp.events_msg(
        _button_event(fob, button=EventButtonType.ALARM_HUB_BUTTON),
        EventChange.STARTED,
    )
    await hass.async_block_till_done()

    assert len(events) == 1
    assert events[0].data["new_state"].attributes["event_type"] == "alarm_hub_button"
    unsub()


async def test_fob_button_press_without_metadata_is_ignored(
    hass: HomeAssistant,
    ufp_with_fob: tuple[MockUFPFixture, Mock],
) -> None:
    """A button-press event carrying no button metadata does not fire."""
    ufp, fob = ufp_with_fob
    await init_entry(hass, ufp, [])

    events: list[HAEvent] = []

    @callback
    def _capture(event: HAEvent) -> None:
        events.append(event)

    unsub = async_track_state_change_event(hass, BUTTON_EVENT, _capture)

    ufp.events_msg(
        ProtectEvent(
            id="evt-nometa",
            type=EventType.ALARM_HUB_BUTTON_PRESS,
            channel=ProtectEventChannel.ALARM_HUB,
            device_id=fob.id,
            device_mac=fob.mac,
            start=datetime(2026, 1, 1) - timedelta(seconds=1),
            end=datetime(2026, 1, 1),
            metadata=None,
        ),
        EventChange.STARTED,
    )
    await hass.async_block_till_done()

    assert len(events) == 0
    unsub()


async def test_fob_battery_updates_from_public_ws(
    hass: HomeAssistant,
    ufp_with_fob: tuple[MockUFPFixture, Mock],
) -> None:
    """A public devices WS update for the fob refreshes the battery sensor."""
    ufp, fob = ufp_with_fob
    await init_entry(hass, ufp, [])

    assert hass.states.get(BATTERY_SENSOR).state == "80"

    fob.wireless_connection_state = PublicWirelessConnectionState(
        battery_status=PublicWirelessBatteryStatus(percentage=42, is_low=False),
        signal_state=PublicSignalState(signal_strength=-55, signal_quality=None),
    )

    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.old_obj = fob
    mock_msg.new_obj = fob
    assert ufp.devices_ws_subscription is not None
    ufp.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    assert hass.states.get(BATTERY_SENSOR).state == "42"


async def test_fob_unavailable_on_public_ws_disconnect(
    hass: HomeAssistant,
    ufp_with_fob: tuple[MockUFPFixture, Mock],
) -> None:
    """Fob entities go unavailable when the public websocket disconnects."""
    ufp, _fob = ufp_with_fob
    await init_entry(hass, ufp, [])

    assert hass.states.get(BATTERY_SENSOR).state == "80"

    assert ufp.devices_ws_state_subscription is not None
    ufp.devices_ws_state_subscription(WebsocketState.DISCONNECTED)
    await hass.async_block_till_done()

    assert hass.states.get(BATTERY_SENSOR).state == STATE_UNAVAILABLE


async def test_fob_battery_none_is_unknown(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """A freshly-paired fob reporting null battery yields an unknown state."""
    fob = _make_fob(percentage=None)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(fob)

    await init_entry(hass, ufp, [])

    state = hass.states.get(BATTERY_SENSOR)
    assert state is not None
    assert state.state == "unknown"


async def test_fob_signal_sensor_when_enabled(
    hass: HomeAssistant,
    ufp_with_fob: tuple[MockUFPFixture, Mock],
) -> None:
    """Enabling the signal-strength sensor exposes the fob's signal value."""
    ufp, _fob = ufp_with_fob
    await init_entry(hass, ufp, [])

    await enable_entity(hass, ufp.entry.entry_id, SIGNAL_SENSOR)

    state = hass.states.get(SIGNAL_SENSOR)
    assert state is not None
    assert state.state == "-55"


async def test_fob_event_entity_created_with_empty_feature_flags(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """A fob with empty feature_flags (real hardware) still gets an event entity."""
    fob = _make_fob(buttons=[])
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(fob)

    await init_entry(hass, ufp, [])

    state = hass.states.get(BUTTON_EVENT)
    assert state is not None
    assert "arm" in state.attributes["event_types"]


async def test_fob_status_reflects_away_state(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """The status sensor reflects a lost fob's away state."""
    fob = _make_fob(away_state=FobAwayState.DEVICE_LOST)
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(fob)

    await init_entry(hass, ufp, [])

    state = hass.states.get(STATUS_SENSOR)
    assert state is not None
    assert state.state == "device_lost"


async def test_fob_unavailable_when_removed_from_bootstrap(
    hass: HomeAssistant,
    ufp_with_fob: tuple[MockUFPFixture, Mock],
) -> None:
    """A fob deleted from the public bootstrap marks its entities unavailable."""
    ufp, fob = ufp_with_fob
    await init_entry(hass, ufp, [])

    assert hass.states.get(BATTERY_SENSOR).state == "80"

    # Delete event: the library removes the object before dispatching ``None``.
    del ufp.api.public_bootstrap.fobs[fob.id]
    mock_msg = Mock()
    mock_msg.old_obj = fob
    mock_msg.new_obj = None
    assert ufp.devices_ws_subscription is not None
    ufp.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(BATTERY_SENSOR)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_fob_without_wireless_data_is_unknown(
    hass: HomeAssistant,
    ufp: MockUFPFixture,
) -> None:
    """A freshly-paired fob with no battery/signal reported reads as unknown."""
    fob = _make_fob()
    fob.wireless_connection_state = PublicWirelessConnectionState(
        battery_status=None, signal_state=None
    )
    ufp.api.has_public_bootstrap = True
    ufp.api.public_bootstrap = _make_public_bootstrap(fob)

    await init_entry(hass, ufp, [])

    assert hass.states.get(BATTERY_SENSOR).state == "unknown"
    assert hass.states.get(BATTERY_LOW_BINARY).state == "unknown"

    await enable_entity(hass, ufp.entry.entry_id, SIGNAL_SENSOR)
    assert hass.states.get(SIGNAL_SENSOR).state == "unknown"


async def test_fob_unavailable_when_public_bootstrap_lost(
    hass: HomeAssistant,
    ufp_with_fob: tuple[MockUFPFixture, Mock],
) -> None:
    """Losing the public bootstrap marks fob entities unavailable."""
    ufp, fob = ufp_with_fob
    await init_entry(hass, ufp, [])

    assert hass.states.get(BATTERY_SENSOR).state == "80"

    ufp.api.has_public_bootstrap = False
    mock_msg = Mock()
    mock_msg.changed_data = {}
    mock_msg.old_obj = fob
    mock_msg.new_obj = fob
    assert ufp.devices_ws_subscription is not None
    ufp.devices_ws_subscription(mock_msg)
    await hass.async_block_till_done()

    state = hass.states.get(BATTERY_SENSOR)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_fob_entity_counts(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    ufp_with_fob: tuple[MockUFPFixture, Mock],
) -> None:
    """Exactly the expected fob entities are created across platforms."""
    ufp, _fob = ufp_with_fob
    await init_entry(hass, ufp, [])

    fob_entities = [
        entry
        for entry in entity_registry.entities.values()
        if entry.unique_id.startswith(FOB_MAC)
    ]
    # battery sensor, signal sensor, status sensor, battery-low binary, button event
    assert len(fob_entities) == 5
    assert sum(not entry.disabled for entry in fob_entities) == 4
