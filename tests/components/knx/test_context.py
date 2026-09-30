"""Test KNX context propagation through Home Assistant automations."""

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
from xknx.telegram import Telegram, TelegramDirection

from homeassistant.components.knx.const import EVENT_KNX_STATE_CHANGED
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import KNXTestKit

from tests.common import async_capture_events, async_fire_time_changed


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
                            "target": {"entity_id": "cover.test"},
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
    assert hass.states.get("cover.test").context is action_context
    assert len(events) == 1

    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("cover.test").state == "closing"
    assert hass.states.get("cover.test").context is action_context
    freezer.tick(timedelta(seconds=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    await knx.assert_write("2/0/2", True)
    assert len(outgoing) == 2
    assert all(telegram.context is action_context for telegram in outgoing)
    cover_states = [
        event.data["new_state"]
        for event in states
        if event.data["entity_id"] == "cover.test"
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
    assert hass.states.get("cover.test").context is events[0].context
    freezer.tick(timedelta(seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get("cover.test").context is events[0].context
    assert len(events) == 1
