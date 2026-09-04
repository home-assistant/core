"""The tests for the Group Automation platform."""

import asyncio

from homeassistant.components.automation import (
    CONF_STOP_ACTIONS,
    DOMAIN as AUTOMATION_DOMAIN,
    SERVICE_TRIGGER,
)
from homeassistant.components.group import DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TOGGLE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_mock_service


async def _async_setup_automations(hass: HomeAssistant) -> None:
    """Set up two automations to use as group members."""
    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "id": "one",
                    "alias": "One",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": [],
                },
                {
                    "id": "two",
                    "alias": "Two",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": [],
                },
            ]
        },
    )
    await hass.async_block_till_done()


async def _async_setup_automation_group(
    hass: HomeAssistant, entities: list[str], all_mode: bool = False
) -> None:
    """Set up an automation group config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        options={
            "group_type": "automation",
            "name": "Automation Group",
            "entities": entities,
            "all": all_mode,
            "hide_members": False,
        },
        title="Automation Group",
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def test_default_state(hass: HomeAssistant) -> None:
    """Test automation group default state."""
    await _async_setup_automations(hass)
    await _async_setup_automation_group(hass, ["automation.one", "automation.two"])

    state = hass.states.get("automation.automation_group")
    assert state is not None
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ENTITY_ID) == [
        "automation.one",
        "automation.two",
    ]


async def test_state_reporting(hass: HomeAssistant) -> None:
    """Test the state reporting in 'any' mode.

    The group state is unavailable if all group members are unavailable.
    Otherwise, the group state is unknown if all group members are unknown.
    Otherwise, the group state is on if at least one group member is on.
    Otherwise, the group state is off.
    """
    await _async_setup_automation_group(hass, ["automation.test1", "automation.test2"])

    assert hass.states.get("automation.automation_group").state == STATE_UNAVAILABLE

    hass.states.async_set("automation.test1", STATE_UNAVAILABLE)
    hass.states.async_set("automation.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("automation.automation_group").state == STATE_UNAVAILABLE

    hass.states.async_set("automation.test1", STATE_UNKNOWN)
    hass.states.async_set("automation.test2", STATE_UNKNOWN)
    await hass.async_block_till_done()
    assert hass.states.get("automation.automation_group").state == STATE_UNKNOWN

    hass.states.async_set("automation.test1", STATE_ON)
    hass.states.async_set("automation.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("automation.automation_group").state == STATE_ON

    hass.states.async_set("automation.test1", STATE_OFF)
    hass.states.async_set("automation.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("automation.automation_group").state == STATE_OFF

    hass.states.async_remove("automation.test1")
    hass.states.async_remove("automation.test2")
    await hass.async_block_till_done()
    assert hass.states.get("automation.automation_group").state == STATE_UNAVAILABLE


async def test_state_reporting_all(hass: HomeAssistant) -> None:
    """Test the state reporting in 'all' mode.

    The group state is unavailable if all group members are unavailable.
    Otherwise, the group state is unknown if at least one group member
    is unknown or unavailable.
    Otherwise, the group state is off if at least one group member is
    off.
    Otherwise, the group state is on.
    """
    await _async_setup_automation_group(
        hass, ["automation.test1", "automation.test2"], all_mode=True
    )

    assert hass.states.get("automation.automation_group").state == STATE_UNAVAILABLE

    hass.states.async_set("automation.test1", STATE_ON)
    hass.states.async_set("automation.test2", STATE_UNAVAILABLE)
    await hass.async_block_till_done()
    assert hass.states.get("automation.automation_group").state == STATE_UNKNOWN

    hass.states.async_set("automation.test1", STATE_ON)
    hass.states.async_set("automation.test2", STATE_OFF)
    await hass.async_block_till_done()
    assert hass.states.get("automation.automation_group").state == STATE_OFF

    hass.states.async_set("automation.test1", STATE_ON)
    hass.states.async_set("automation.test2", STATE_ON)
    await hass.async_block_till_done()
    assert hass.states.get("automation.automation_group").state == STATE_ON


async def test_service_calls(hass: HomeAssistant) -> None:
    """Test service calls are forwarded to automation group members."""
    await _async_setup_automations(hass)
    await _async_setup_automation_group(hass, ["automation.one", "automation.two"])

    group_state = hass.states.get("automation.automation_group")
    assert group_state.state == STATE_ON

    await hass.services.async_call(
        AUTOMATION_DOMAIN,
        SERVICE_TOGGLE,
        {ATTR_ENTITY_ID: "automation.automation_group"},
        blocking=True,
    )
    assert hass.states.get("automation.one").state == STATE_OFF
    assert hass.states.get("automation.two").state == STATE_OFF

    await hass.services.async_call(
        AUTOMATION_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "automation.automation_group"},
        blocking=True,
    )
    assert hass.states.get("automation.one").state == STATE_ON
    assert hass.states.get("automation.two").state == STATE_ON

    await hass.services.async_call(
        AUTOMATION_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "automation.automation_group"},
        blocking=True,
    )
    assert hass.states.get("automation.one").state == STATE_OFF
    assert hass.states.get("automation.two").state == STATE_OFF


async def test_trigger_service_forwarded(hass: HomeAssistant) -> None:
    """Test the trigger service is forwarded to automation group members."""
    calls = async_mock_service(hass, "test", "automation")

    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "id": "one",
                    "alias": "One",
                    # This trigger never fires on its own, so any recorded
                    # call can only come from the forwarded trigger service.
                    "trigger": {"platform": "event", "event_type": "never_fired"},
                    "action": {"action": "test.automation"},
                }
            ]
        },
    )
    await hass.async_block_till_done()
    await _async_setup_automation_group(hass, ["automation.one"])

    await hass.services.async_call(
        AUTOMATION_DOMAIN,
        SERVICE_TRIGGER,
        {ATTR_ENTITY_ID: "automation.automation_group"},
        blocking=True,
    )

    assert len(calls) == 1


async def test_turn_off_stop_actions_forwarded(hass: HomeAssistant) -> None:
    """Test the stop_actions option is forwarded when turning off the group."""
    calls = async_mock_service(hass, "test", "automation")
    test_entity = "test.entity"

    assert await async_setup_component(
        hass,
        AUTOMATION_DOMAIN,
        {
            AUTOMATION_DOMAIN: [
                {
                    "id": "one",
                    "alias": "One",
                    "trigger": {"platform": "event", "event_type": "test_event"},
                    "action": [
                        {"event": "running"},
                        {"wait_template": "{{ is_state('test.entity', 'goodbye') }}"},
                        {"action": "test.automation"},
                    ],
                }
            ]
        },
    )
    await _async_setup_automation_group(hass, ["automation.one"])

    running = asyncio.Event()

    @callback
    def running_cb(event):
        running.set()

    hass.bus.async_listen_once("running", running_cb)
    hass.states.async_set(test_entity, "hello")

    hass.bus.async_fire("test_event")
    await running.wait()

    await hass.services.async_call(
        AUTOMATION_DOMAIN,
        SERVICE_TURN_OFF,
        {
            ATTR_ENTITY_ID: "automation.automation_group",
            CONF_STOP_ACTIONS: False,
        },
        blocking=True,
    )

    hass.states.async_set(test_entity, "goodbye")
    await hass.async_block_till_done()

    assert len(calls) == 1
