"""Test KNX context propagation through Home Assistant automations."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import async_capture_events, async_fire_time_changed
from xknx.telegram import Telegram, TelegramDirection

from homeassistant.components.knx.const import EVENT_KNX_STATE_CHANGED
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from .conftest import KNXTestKit

LIGHT_ENTITY_ID = "light.test"
SWITCH_ENTITY_ID = "switch.test"
COVER_ENTITY_ID = "cover.test"


async def test_knx_automation_cover_context(
    hass: HomeAssistant,
    knx: KNXTestKit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Keep automation attribution through travel beyond HA's recent-context window."""
    await knx.setup_integration(
        {
            "switch": {"name": "trigger", "address": "1/1/1"},
            "cover": {
                "name": "test",
                "move_long_address": "2/0/1",
                "stop_address": "2/0/2",
                "position_state_address": "2/0/4",
                "travelling_time_down": 12,
                "travelling_time_up": 12,
            },
        },
        state_updater=False,
    )
    await knx.receive_response("2/0/4", (0,))
    await knx.receive_response("1/1/1", False)
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "KNX switch moves cover",
                    "triggers": [
                        {"trigger": "state", "entity_id": "switch.trigger", "to": "on"}
                    ],
                    "actions": [
                        {
                            "action": "cover.set_cover_position",
                            "target": {"entity_id": COVER_ENTITY_ID},
                            "data": {"position": 50},
                        }
                    ],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    automations = async_capture_events(hass, "automation_triggered")
    states = async_capture_events(hass, "state_changed")
    outgoing: list[Telegram] = []

    def collect(telegram: Telegram) -> None:
        if telegram.direction is TelegramDirection.OUTGOING:
            outgoing.append(telegram)

    knx.xknx.telegram_queue.register_telegram_received_cb(
        collect, match_for_outgoing=True
    )
    freezer.tick(timedelta(seconds=1))
    await knx.receive_write("1/1/1", True, source="1.1.23")
    await knx.assert_write("2/0/1", True)
    assert len(automations) == 1
    action_context = automations[0].context
    assert action_context.parent_id == events[0].context.id
    assert hass.states.get(COVER_ENTITY_ID).context is action_context
    assert len(events) == 1

    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(COVER_ENTITY_ID).state == "closing"
    assert hass.states.get(COVER_ENTITY_ID).context is action_context
    freezer.tick(timedelta(seconds=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await knx.assert_write("2/0/2", True)
    assert len(outgoing) == 2
    assert all(telegram.context is action_context for telegram in outgoing)
    cover_states = [
        event.data["new_state"]
        for event in states
        if event.data["entity_id"] == COVER_ENTITY_ID
    ]
    assert len(cover_states) >= 3
    assert all(state.context.id == action_context.id for state in cover_states)
    assert len(events) == 1


async def test_direct_cover_sender(
    hass: HomeAssistant, knx: KNXTestKit, freezer: FrozenDateTimeFactory
) -> None:
    """One incoming telegram retains its sender across delayed travel updates."""
    await knx.setup_integration(
        {
            "cover": {
                "name": "test",
                "move_long_address": "2/0/1",
                "position_state_address": "2/0/4",
                "travelling_time_down": 12,
            }
        },
        state_updater=False,
    )
    await knx.receive_response("2/0/4", (0,))
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    await knx.receive_write("2/0/1", True, source="1.1.24")
    assert len(events) == 1
    assert hass.states.get(COVER_ENTITY_ID).context is events[0].context
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(COVER_ENTITY_ID).context is events[0].context
    assert len(events) == 1


@pytest.mark.parametrize(
    (
        "platform",
        "config",
        "initial_payload",
        "service_name",
        "service_data",
        "write_payload",
        "feedback_payload",
        "expected_state",
    ),
    [
        pytest.param(
            "light",
            {
                "address": "1/1/1",
                "state_address": "1/1/2",
                "brightness_address": "1/1/3",
            },
            False,
            "turn_on",
            {"brightness": 128},
            (128,),
            True,
            "on",
            id="dimmer",
        ),
        pytest.param(
            "cover",
            {
                "move_long_address": "1/1/1",
                "position_address": "1/1/3",
                "position_state_address": "1/1/2",
            },
            (0,),
            "set_cover_position",
            {"position": 0},
            (255,),
            (255,),
            "closed",
            id="cover",
        ),
    ],
)
async def test_service_feedback_context(
    hass: HomeAssistant,
    knx: KNXTestKit,
    freezer: FrozenDateTimeFactory,
    platform: str,
    config: ConfigType,
    initial_payload: int | tuple[int, ...],
    service_name: str,
    service_data: dict[str, int],
    write_payload: int | tuple[int, ...],
    feedback_payload: int | tuple[int, ...],
    expected_state: str,
) -> None:
    """Actuator feedback completing an HA action retains its cause."""
    await knx.setup_integration(
        {platform: {"name": "test", **config}}, state_updater=False
    )
    await knx.receive_response("1/1/2", initial_payload)
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    context = Context(parent_id=Context().id)
    entity_id = f"{platform}.test"
    await hass.services.async_call(
        platform,
        service_name,
        {"entity_id": entity_id, **service_data},
        blocking=True,
        context=context,
    )
    await knx.assert_write("1/1/3", write_payload)
    freezer.tick(timedelta(milliseconds=100))
    await knx.receive_write("1/1/2", feedback_payload, source="1.1.40")
    assert hass.states.get(entity_id).state == expected_state
    assert hass.states.get(entity_id).context is context
    assert not events


async def test_brightness_feedback_automation_context(
    hass: HomeAssistant, knx: KNXTestKit, freezer: FrozenDateTimeFactory
) -> None:
    """Attribute feedback preserves automation ancestry without extending the window."""
    await knx.setup_integration(
        {
            "light": {
                "name": "test",
                "address": "1/1/1",
                "brightness_address": "1/1/3",
                "brightness_state_address": "1/1/4",
            }
        },
        state_updater=False,
    )
    await knx.receive_response("1/1/1", False)
    await knx.receive_response("1/1/4", (0,))
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "alias": "Brightness observer",
                    "triggers": [
                        {
                            "trigger": "numeric_state",
                            "entity_id": LIGHT_ENTITY_ID,
                            "attribute": "brightness",
                            "above": 100,
                        }
                    ],
                    "actions": [{"event": "brightness_observed"}],
                }
            ]
        },
    )
    await hass.async_block_till_done()
    automations = async_capture_events(hass, "automation_triggered")
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    context = Context(parent_id=Context().id)
    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": LIGHT_ENTITY_ID},
        blocking=True,
        context=context,
    )
    await knx.assert_write("1/1/1", True)
    freezer.tick(timedelta(seconds=4))
    await knx.receive_write("1/1/4", (128,), source="1.1.40")
    assert len(automations) == 1
    assert automations[0].context.parent_id == context.id
    assert hass.states.get(LIGHT_ENTITY_ID).context is context
    assert not events
    freezer.tick(timedelta(seconds=2))
    await knx.receive_write("1/1/1", False, source="1.1.23")
    assert len(events) == 1
    assert hass.states.get(LIGHT_ENTITY_ID).context is events[0].context


@pytest.mark.parametrize("elapsed", [0, 10])
async def test_direct_action_does_not_reuse_sender(
    hass: HomeAssistant, knx: KNXTestKit, freezer: FrozenDateTimeFactory, elapsed: int
) -> None:
    """A new action without a service context must not inherit a KNX sender."""
    await knx.setup_integration(
        {"switch": {"name": "test", "address": "1/1/1"}}, state_updater=False
    )
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    await knx.receive_write("1/1/1", True, source="1.1.23")
    previous = hass.states.get(SWITCH_ENTITY_ID).context
    entity = hass.data["switch"].get_entity(SWITCH_ENTITY_ID)
    freezer.tick(timedelta(seconds=elapsed))
    await entity.async_turn_off()
    await knx.assert_write("1/1/1", False)
    assert hass.states.get(SWITCH_ENTITY_ID).state == "off"
    assert hass.states.get(SWITCH_ENTITY_ID).context.id != previous.id
    assert len(events) == 1


async def test_direct_action_does_not_reuse_expired_service(
    hass: HomeAssistant, knx: KNXTestKit, freezer: FrozenDateTimeFactory
) -> None:
    """Feedback must not make an expired service context valid for a new action."""
    await knx.setup_integration(
        {"switch": {"name": "test", "address": "1/1/1"}}, state_updater=False
    )
    context = Context(parent_id=Context().id)
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": SWITCH_ENTITY_ID},
        blocking=True,
        context=context,
    )
    await knx.assert_write("1/1/1", True)
    freezer.tick(timedelta(seconds=10))
    entity = hass.data["switch"].get_entity(SWITCH_ENTITY_ID)
    await entity.async_turn_off()
    await knx.assert_write("1/1/1", False)
    state = hass.states.get(SWITCH_ENTITY_ID)
    assert state.state == "off"
    assert state.context.id != context.id
    assert state.context.parent_id is None


@pytest.mark.parametrize("platform", ["light", "switch"])
@pytest.mark.parametrize("elapsed", [0, 1, 4])
async def test_command_supersedes_recent_service(
    hass: HomeAssistant,
    knx: KNXTestKit,
    freezer: FrozenDateTimeFactory,
    platform: str,
    elapsed: int,
) -> None:
    """A physical command takes over even while the HA service is recent."""
    await knx.setup_integration(
        {platform: {"name": "test", "address": "1/1/1", "state_address": "1/1/2"}},
        state_updater=False,
    )
    await knx.receive_response("1/1/2", False)
    context = Context(parent_id=Context().id)
    entity_id = f"{platform}.test"
    await hass.services.async_call(
        platform, "turn_on", {"entity_id": entity_id}, blocking=True, context=context
    )
    await knx.assert_write("1/1/1", True)
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    freezer.tick(timedelta(seconds=elapsed))
    await knx.receive_write("1/1/1", False, source="1.1.23")
    assert len(events) == 1
    assert hass.states.get(entity_id).context is events[0].context
    assert events[0].data["source"] == "1.1.23"

    # An autonomous actuator change must not resurrect the superseded HA cause.
    await knx.receive_write("1/1/2", True, source="1.1.40")
    assert len(events) == 2
    assert hass.states.get(entity_id).context is events[1].context
    assert events[1].data["source"] == "1.1.40"


@pytest.fixture
async def moving_cover(hass: HomeAssistant, knx: KNXTestKit) -> Context:
    """Start a sixty-second HA cover movement with a known position."""
    await knx.setup_integration(
        {
            "cover": {
                "name": "test",
                "move_long_address": ["2/0/1", "2/0/8"],
                "stop_address": "2/0/2",
                "position_state_address": "2/0/4",
                "travelling_time_down": 60,
                "travelling_time_up": 60,
            }
        },
        state_updater=False,
    )
    await knx.receive_response("2/0/4", (0,))
    context = Context(parent_id=Context().id)
    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": COVER_ENTITY_ID},
        blocking=True,
        context=context,
    )
    await knx.assert_write("2/0/1", True)
    assert hass.states.get(COVER_ENTITY_ID).context is context
    return context


async def test_cover_late_feedback(
    hass: HomeAssistant,
    knx: KNXTestKit,
    freezer: FrozenDateTimeFactory,
    moving_cover: Context,
) -> None:
    """Final feedback keeps the HA cause after a long movement."""
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    freezer.tick(timedelta(seconds=59.5))
    await knx.receive_write("2/0/4", (255,), source="1.1.40")
    assert hass.states.get(COVER_ENTITY_ID).state == "closed"
    assert hass.states.get(COVER_ENTITY_ID).context is moving_cover
    assert not events


@pytest.mark.parametrize(("elapsed", "preserved"), [(0.5, True), (2, False)])
async def test_cover_feedback_after_calculated_end(
    hass: HomeAssistant,
    knx: KNXTestKit,
    freezer: FrozenDateTimeFactory,
    moving_cover: Context,
    elapsed: float,
    preserved: bool,
) -> None:
    """Feedback has a bounded grace period after the calculated end."""
    freezer.tick(timedelta(seconds=60))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(COVER_ENTITY_ID).state == "closed"
    freezer.tick(timedelta(seconds=elapsed))
    await knx.receive_write("2/0/4", (128,), source="1.1.40")
    assert (hass.states.get(COVER_ENTITY_ID).context is moving_cover) is preserved


@pytest.mark.parametrize("address", ["2/0/1", "2/0/8"])
async def test_cover_direction_change_and_feedback(
    hass: HomeAssistant,
    knx: KNXTestKit,
    freezer: FrozenDateTimeFactory,
    moving_cover: Context,
    address: str,
) -> None:
    """A direct or passive command replaces the cause and travel deadline."""
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    freezer.tick(timedelta(seconds=1))
    await knx.receive_write(address, False, source="1.1.23")
    assert hass.states.get(COVER_ENTITY_ID).state == "opening"
    assert len(events) == 1
    manual_context = events[0].context
    assert manual_context is not moving_cover
    assert hass.states.get(COVER_ENTITY_ID).context is manual_context
    freezer.tick(timedelta(seconds=0.5))
    await knx.receive_write("2/0/4", (0,), source="1.1.40")
    assert hass.states.get(COVER_ENTITY_ID).context is manual_context
    assert len(events) == 1
    freezer.tick(timedelta(seconds=3))
    await knx.receive_write("2/0/4", (255,), source="1.1.40")
    assert hass.states.get(COVER_ENTITY_ID).context is events[-1].context
    assert events[-1].data["source"] == "1.1.40"
    assert len(events) == 2


async def test_cover_stop_and_feedback(
    hass: HomeAssistant,
    knx: KNXTestKit,
    freezer: FrozenDateTimeFactory,
    moving_cover: Context,
) -> None:
    """A stop replaces the service cause and shortens the feedback window."""
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    freezer.tick(timedelta(seconds=1))
    await knx.receive_write("2/0/2", True, source="1.1.23")
    assert hass.states.get(COVER_ENTITY_ID).state == "open"
    assert len(events) == 1
    manual_context = events[0].context
    assert manual_context is not moving_cover
    assert hass.states.get(COVER_ENTITY_ID).context is manual_context
    freezer.tick(timedelta(seconds=0.5))
    await knx.receive_write("2/0/4", (4,), source="1.1.40")
    assert hass.states.get(COVER_ENTITY_ID).context is manual_context
    freezer.tick(timedelta(seconds=1))
    await knx.receive_write("2/0/4", (255,), source="1.1.40")
    assert hass.states.get(COVER_ENTITY_ID).context is events[-1].context
    assert events[-1].data["source"] == "1.1.40"
    assert len(events) == 2


async def test_cover_feedback_does_not_extend_deadline(
    hass: HomeAssistant,
    knx: KNXTestKit,
    freezer: FrozenDateTimeFactory,
    moving_cover: Context,
) -> None:
    """Intermediate position reports cannot keep an old cause alive forever."""
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    freezer.tick(timedelta(seconds=59))
    await knx.receive_write("2/0/4", (128,), source="1.1.40")
    assert hass.states.get(COVER_ENTITY_ID).context is moving_cover
    freezer.tick(timedelta(seconds=3))
    await knx.receive_write("2/0/4", (255,), source="1.1.40")
    assert len(events) == 1
    assert hass.states.get(COVER_ENTITY_ID).context is events[0].context
    assert events[0].data["source"] == "1.1.40"


async def test_new_cover_service_replaces_travel_cause(
    hass: HomeAssistant,
    knx: KNXTestKit,
    freezer: FrozenDateTimeFactory,
    moving_cover: Context,
) -> None:
    """A second HA action supersedes the cause and deadline of the first."""
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    freezer.tick(timedelta(seconds=10))
    context = Context(parent_id=Context().id)
    await hass.services.async_call(
        "cover",
        "open_cover",
        {"entity_id": COVER_ENTITY_ID},
        blocking=True,
        context=context,
    )
    await knx.assert_write("2/0/1", False)
    assert context is not moving_cover
    assert hass.states.get(COVER_ENTITY_ID).context is context
    freezer.tick(timedelta(seconds=9.5))
    await knx.receive_write("2/0/4", (0,), source="1.1.40")
    assert hass.states.get(COVER_ENTITY_ID).context is context
    assert not events
    freezer.tick(timedelta(seconds=3))
    await knx.receive_write("2/0/4", (255,), source="1.1.40")
    assert len(events) == 1
    assert hass.states.get(COVER_ENTITY_ID).context is events[0].context


async def test_unknown_cover_position_has_no_long_feedback_window(
    hass: HomeAssistant,
    knx: KNXTestKit,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Without an estimated travel, late feedback does not claim the HA cause."""
    await knx.setup_integration(
        {
            "cover": {
                "name": "test",
                "move_long_address": "2/0/1",
                "position_state_address": "2/0/4",
            }
        },
        state_updater=False,
    )
    context = Context(parent_id=Context().id)
    await hass.services.async_call(
        "cover",
        "close_cover",
        {"entity_id": COVER_ENTITY_ID},
        blocking=True,
        context=context,
    )
    await knx.assert_write("2/0/1", True)
    freezer.tick(timedelta(seconds=10))
    await knx.receive_write("2/0/4", (128,), source="1.1.40")
    assert hass.states.get(COVER_ENTITY_ID).context is not context


@pytest.mark.parametrize("platform", ["light", "switch"])
@pytest.mark.parametrize("state_address", ["1/1/2", "1/1/4"])
async def test_feedback_window_does_not_slide(
    hass: HomeAssistant,
    knx: KNXTestKit,
    freezer: FrozenDateTimeFactory,
    platform: str,
    state_address: str,
) -> None:
    """Active and passive status addresses retain only a recent service cause."""
    await knx.setup_integration(
        {
            platform: {
                "name": "test",
                "address": "1/1/1",
                "state_address": ["1/1/2", "1/1/4"],
            }
        },
        state_updater=False,
    )
    await knx.receive_response("1/1/2", False)
    entity_id = f"{platform}.test"
    context = Context(parent_id=Context().id)
    await hass.services.async_call(
        platform,
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
        context=context,
    )
    await knx.assert_write("1/1/1", True)
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    freezer.tick(timedelta(seconds=4))
    await knx.receive_write(state_address, False, source="1.1.40")
    assert hass.states.get(entity_id).context is context
    assert not events
    freezer.tick(timedelta(seconds=2))
    await knx.receive_write(state_address, True, source="1.1.40")
    assert len(events) == 1
    assert hass.states.get(entity_id).context is events[0].context


@pytest.mark.parametrize("platform", ["light", "switch"])
async def test_shared_command_status_address_is_command(
    hass: HomeAssistant,
    knx: KNXTestKit,
    platform: str,
) -> None:
    """A shared address cannot distinguish feedback from a new command."""
    await knx.setup_integration(
        {platform: {"name": "test", "address": "1/1/1", "state_address": "1/1/1"}},
        state_updater=False,
    )
    await knx.receive_response("1/1/1", False)
    entity_id = f"{platform}.test"
    context = Context(parent_id=Context().id)
    await hass.services.async_call(
        platform,
        "turn_on",
        {"entity_id": entity_id},
        blocking=True,
        context=context,
    )
    await knx.assert_write("1/1/1", True)
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    await knx.receive_write("1/1/1", False, source="1.1.40")
    assert len(events) == 1
    assert hass.states.get(entity_id).context is events[0].context
    assert events[0].data["source"] == "1.1.40"


async def test_bus_cover_cause_survives_long_travel(
    hass: HomeAssistant,
    knx: KNXTestKit,
    freezer: FrozenDateTimeFactory,
    moving_cover: Context,
) -> None:
    """Late feedback keeps the wall switch cause after a manually restarted travel."""
    events = async_capture_events(hass, EVENT_KNX_STATE_CHANGED)
    freezer.tick(timedelta(seconds=1))
    await knx.receive_write("2/0/2", True, source="1.1.23")
    await knx.receive_write("2/0/1", True, source="1.1.24")
    assert len(events) == 2
    manual_context = events[1].context
    assert manual_context is not moving_cover
    assert hass.states.get(COVER_ENTITY_ID).context is manual_context
    freezer.tick(timedelta(seconds=58.5))
    await knx.receive_write("2/0/4", (255,), source="1.1.40")
    assert hass.states.get(COVER_ENTITY_ID).state == "closed"
    assert hass.states.get(COVER_ENTITY_ID).context is manual_context
    assert len(events) == 2
    assert events[1].data["source"] == "1.1.24"
