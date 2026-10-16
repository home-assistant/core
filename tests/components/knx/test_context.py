"""Test KNX context propagation through Home Assistant automations."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from xknx.telegram import Telegram, TelegramDirection

from homeassistant.components.knx.const import EVENT_KNX_STATE_CHANGED
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers.typing import ConfigType
from homeassistant.setup import async_setup_component

from .conftest import KNXTestKit

from tests.common import async_capture_events, async_fire_time_changed

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
