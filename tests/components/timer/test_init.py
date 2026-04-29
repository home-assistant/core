"""The tests for the timer component."""

from datetime import timedelta
import logging
from typing import Any
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.timer import (
    ATTR_DURATION,
    ATTR_FINISHES_AT,
    ATTR_LAST_ACTION,
    ATTR_REMAINING,
    ATTR_RESTORE,
    CONF_DURATION,
    CONF_ICON,
    CONF_NAME,
    CONF_RESTORE,
    DEFAULT_DURATION,
    DOMAIN,
    EVENT_TIMER_CANCELLED,
    EVENT_TIMER_CHANGED,
    EVENT_TIMER_FINISHED,
    EVENT_TIMER_PAUSED,
    EVENT_TIMER_RESTARTED,
    EVENT_TIMER_STARTED,
    SERVICE_CANCEL,
    SERVICE_CHANGE,
    SERVICE_FINISH,
    SERVICE_PAUSE,
    SERVICE_START,
    STATUS_ACTIVE,
    STATUS_IDLE,
    STATUS_PAUSED,
    Timer,
)
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_ID,
    ATTR_NAME,
    CONF_ENTITY_ID,
    CONF_ID,
    EVENT_STATE_CHANGED,
    SERVICE_RELOAD,
)
from homeassistant.core import Context, CoreState, Event, HomeAssistant, State, callback
from homeassistant.exceptions import HomeAssistantError, Unauthorized
from homeassistant.helpers import config_validation as cv, entity_registry as er
from homeassistant.helpers.restore_state import StoredState, async_get
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import MockUser, async_capture_events, async_fire_time_changed
from tests.typing import WebSocketGenerator

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def storage_setup(hass: HomeAssistant, hass_storage: dict[str, Any]):
    """Storage setup."""

    async def _storage(items=None, config=None):
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {
                    "items": [
                        {
                            ATTR_ID: "from_storage",
                            ATTR_NAME: "timer from storage",
                            ATTR_DURATION: "0:00:00",
                            ATTR_RESTORE: False,
                        }
                    ]
                },
            }
        else:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {"items": items},
            }
        if config is None:
            config = {DOMAIN: {}}
        return await async_setup_component(hass, DOMAIN, config)

    return _storage


@pytest.mark.parametrize("invalid_config", [None, 1, {"name with space": None}])
async def test_config(hass: HomeAssistant, invalid_config) -> None:
    """Test config."""

    assert not await async_setup_component(hass, DOMAIN, {DOMAIN: invalid_config})


async def test_config_options(hass: HomeAssistant) -> None:
    """Test configuration options."""
    count_start = len(hass.states.async_entity_ids())

    _LOGGER.debug("ENTITIES @ start: %s", hass.states.async_entity_ids())

    config = {
        DOMAIN: {
            "test_1": {},
            "test_2": {
                CONF_NAME: "Hello World",
                CONF_ICON: "mdi:work",
                CONF_DURATION: 10,
            },
            "test_3": None,
        }
    }

    assert await async_setup_component(hass, "timer", config)
    await hass.async_block_till_done()

    assert count_start + 3 == len(hass.states.async_entity_ids())
    await hass.async_block_till_done()

    state_1 = hass.states.get("timer.test_1")
    state_2 = hass.states.get("timer.test_2")
    state_3 = hass.states.get("timer.test_3")

    assert state_1 is not None
    assert state_2 is not None
    assert state_3 is not None

    assert state_1.state == STATUS_IDLE
    assert state_1.attributes == {
        ATTR_DURATION: "0:00:00",
        ATTR_EDITABLE: False,
        ATTR_LAST_ACTION: None,
    }

    assert state_2.state == STATUS_IDLE
    assert state_2.attributes == {
        ATTR_DURATION: "0:00:10",
        ATTR_EDITABLE: False,
        ATTR_FRIENDLY_NAME: "Hello World",
        ATTR_ICON: "mdi:work",
        ATTR_LAST_ACTION: None,
    }

    assert state_3.state == STATUS_IDLE
    assert state_3.attributes == {
        ATTR_DURATION: str(cv.time_period(DEFAULT_DURATION)),
        ATTR_EDITABLE: False,
        ATTR_LAST_ACTION: None,
    }


@pytest.mark.freeze_time("2023-06-05 17:47:50")
async def test_methods_and_events(hass: HomeAssistant) -> None:
    """Test methods and events."""
    hass.set_state(CoreState.starting)

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"test1": {CONF_DURATION: 10}}})

    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_IDLE
    assert state.attributes == {
        ATTR_DURATION: "0:00:10",
        ATTR_EDITABLE: False,
        ATTR_LAST_ACTION: None,
    }

    results: list[tuple[Event, State | None]] = []

    @callback
    def fake_event_listener(event: Event):
        """Fake event listener for trigger."""
        results.append((event, hass.states.get("timer.test1")))

    hass.bus.async_listen(EVENT_TIMER_STARTED, fake_event_listener)
    hass.bus.async_listen(EVENT_TIMER_RESTARTED, fake_event_listener)
    hass.bus.async_listen(EVENT_TIMER_PAUSED, fake_event_listener)
    hass.bus.async_listen(EVENT_TIMER_FINISHED, fake_event_listener)
    hass.bus.async_listen(EVENT_TIMER_CANCELLED, fake_event_listener)
    hass.bus.async_listen(EVENT_TIMER_CHANGED, fake_event_listener)

    finish_10 = (utcnow() + timedelta(seconds=10)).isoformat()
    finish_5 = (utcnow() + timedelta(seconds=5)).isoformat()

    steps = [
        {
            "call": SERVICE_START,
            "call_data": {},
            "expected_state": STATUS_ACTIVE,
            "expected_extra_attributes": {
                ATTR_FINISHES_AT: finish_10,
                ATTR_LAST_ACTION: "started",
                ATTR_REMAINING: "0:00:10",
            },
            "expected_event": EVENT_TIMER_STARTED,
        },
        {
            "call": SERVICE_PAUSE,
            "call_data": {},
            "expected_state": STATUS_PAUSED,
            "expected_extra_attributes": {
                ATTR_LAST_ACTION: "paused",
                ATTR_REMAINING: "0:00:10",
            },
            "expected_event": EVENT_TIMER_PAUSED,
        },
        {
            "call": SERVICE_START,
            "call_data": {},
            "expected_state": STATUS_ACTIVE,
            "expected_extra_attributes": {
                ATTR_FINISHES_AT: finish_10,
                ATTR_LAST_ACTION: "restarted",
                ATTR_REMAINING: "0:00:10",
            },
            "expected_event": EVENT_TIMER_RESTARTED,
        },
        {
            "call": SERVICE_CANCEL,
            "call_data": {},
            "expected_state": STATUS_IDLE,
            "expected_extra_attributes": {ATTR_LAST_ACTION: "cancelled"},
            "expected_event": EVENT_TIMER_CANCELLED,
        },
        {
            "call": SERVICE_CANCEL,
            "call_data": {},
            "expected_state": STATUS_IDLE,
            "expected_extra_attributes": {ATTR_LAST_ACTION: "cancelled"},
            "expected_event": None,
        },
        {
            "call": SERVICE_START,
            "call_data": {},
            "expected_state": STATUS_ACTIVE,
            "expected_extra_attributes": {
                ATTR_FINISHES_AT: finish_10,
                ATTR_LAST_ACTION: "started",
                ATTR_REMAINING: "0:00:10",
            },
            "expected_event": EVENT_TIMER_STARTED,
        },
        {
            "call": SERVICE_FINISH,
            "call_data": {},
            "expected_state": STATUS_IDLE,
            "expected_extra_attributes": {ATTR_LAST_ACTION: "finished"},
            "expected_event": EVENT_TIMER_FINISHED,
        },
        {
            "call": SERVICE_FINISH,
            "call_data": {},
            "expected_state": STATUS_IDLE,
            "expected_extra_attributes": {ATTR_LAST_ACTION: "finished"},
            "expected_event": None,
        },
        {
            "call": SERVICE_START,
            "call_data": {},
            "expected_state": STATUS_ACTIVE,
            "expected_extra_attributes": {
                ATTR_FINISHES_AT: finish_10,
                ATTR_LAST_ACTION: "started",
                ATTR_REMAINING: "0:00:10",
            },
            "expected_event": EVENT_TIMER_STARTED,
        },
        {
            "call": SERVICE_PAUSE,
            "call_data": {},
            "expected_state": STATUS_PAUSED,
            "expected_extra_attributes": {
                ATTR_LAST_ACTION: "paused",
                ATTR_REMAINING: "0:00:10",
            },
            "expected_event": EVENT_TIMER_PAUSED,
        },
        {
            "call": SERVICE_CANCEL,
            "call_data": {},
            "expected_state": STATUS_IDLE,
            "expected_extra_attributes": {ATTR_LAST_ACTION: "cancelled"},
            "expected_event": EVENT_TIMER_CANCELLED,
        },
        {
            "call": SERVICE_START,
            "call_data": {},
            "expected_state": STATUS_ACTIVE,
            "expected_extra_attributes": {
                ATTR_FINISHES_AT: finish_10,
                ATTR_LAST_ACTION: "started",
                ATTR_REMAINING: "0:00:10",
            },
            "expected_event": EVENT_TIMER_STARTED,
        },
        {
            "call": SERVICE_CHANGE,
            "call_data": {CONF_DURATION: -5},
            "expected_state": STATUS_ACTIVE,
            "expected_extra_attributes": {
                ATTR_FINISHES_AT: finish_5,
                ATTR_LAST_ACTION: "started",  # Change does not set last_action
                ATTR_REMAINING: "0:00:05",
            },
            "expected_event": EVENT_TIMER_CHANGED,
        },
        {
            "call": SERVICE_START,
            "call_data": {},
            "expected_state": STATUS_ACTIVE,
            "expected_extra_attributes": {
                ATTR_FINISHES_AT: finish_5,
                ATTR_LAST_ACTION: "restarted",
                ATTR_REMAINING: "0:00:05",
            },
            "expected_event": EVENT_TIMER_RESTARTED,
        },
        {
            "call": SERVICE_PAUSE,
            "call_data": {},
            "expected_state": STATUS_PAUSED,
            "expected_extra_attributes": {
                ATTR_LAST_ACTION: "paused",
                ATTR_REMAINING: "0:00:05",
            },
            "expected_event": EVENT_TIMER_PAUSED,
        },
        {
            "call": SERVICE_FINISH,
            "call_data": {},
            "expected_state": STATUS_IDLE,
            "expected_extra_attributes": {ATTR_LAST_ACTION: "finished"},
            "expected_event": EVENT_TIMER_FINISHED,
        },
    ]

    expected_events = 0
    for step in steps:
        if step["call"] is not None:
            await hass.services.async_call(
                DOMAIN,
                step["call"],
                {CONF_ENTITY_ID: "timer.test1", **step["call_data"]},
                blocking=True,
            )
            await hass.async_block_till_done()

        state = hass.states.get("timer.test1")
        assert state
        if step["expected_state"] is not None:
            assert state.state == step["expected_state"]
            assert (
                state.attributes
                == {
                    ATTR_DURATION: "0:00:10",
                    ATTR_EDITABLE: False,
                }
                | step["expected_extra_attributes"]
            )

        if step["expected_event"] is not None:
            expected_events += 1
            last_result = results[-1]
            event, state = last_result
            assert event.event_type == step["expected_event"]
            assert state.state == step["expected_state"]
            assert (
                state.attributes
                == {
                    ATTR_DURATION: "0:00:10",
                    ATTR_EDITABLE: False,
                }
                | step["expected_extra_attributes"]
            )
            assert len(results) == expected_events


@pytest.mark.freeze_time("2023-06-05 17:47:50")
async def test_start_service(hass: HomeAssistant) -> None:
    """Test the start/stop service."""
    await async_setup_component(hass, DOMAIN, {DOMAIN: {"test1": {CONF_DURATION: 10}}})

    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_IDLE
    assert state.attributes == {
        ATTR_EDITABLE: False,
        ATTR_DURATION: "0:00:10",
        ATTR_LAST_ACTION: None,
    }

    await hass.services.async_call(
        DOMAIN, SERVICE_START, {CONF_ENTITY_ID: "timer.test1"}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_ACTIVE
    assert state.attributes == {
        ATTR_EDITABLE: False,
        ATTR_DURATION: "0:00:10",
        ATTR_FINISHES_AT: (utcnow() + timedelta(seconds=10)).isoformat(),
        ATTR_LAST_ACTION: "started",
        ATTR_REMAINING: "0:00:10",
    }

    await hass.services.async_call(
        DOMAIN, SERVICE_CANCEL, {CONF_ENTITY_ID: "timer.test1"}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_IDLE
    assert state.attributes == {
        ATTR_EDITABLE: False,
        ATTR_DURATION: "0:00:10",
        ATTR_LAST_ACTION: "cancelled",
    }

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CHANGE,
            {CONF_ENTITY_ID: "timer.test1", CONF_DURATION: 10},
            blocking=True,
        )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_START,
        {CONF_ENTITY_ID: "timer.test1", CONF_DURATION: 15},
        blocking=True,
    )
    await hass.async_block_till_done()
    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_ACTIVE
    assert state.attributes == {
        ATTR_EDITABLE: False,
        ATTR_DURATION: "0:00:15",
        ATTR_FINISHES_AT: (utcnow() + timedelta(seconds=15)).isoformat(),
        ATTR_LAST_ACTION: "started",
        ATTR_REMAINING: "0:00:15",
    }

    with pytest.raises(
        HomeAssistantError,
        match="Not possible to change timer timer.test1 beyond duration",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CHANGE,
            {CONF_ENTITY_ID: "timer.test1", CONF_DURATION: 20},
            blocking=True,
        )

    with pytest.raises(
        HomeAssistantError,
        match="Not possible to change timer timer.test1 to negative time remaining",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CHANGE,
            {CONF_ENTITY_ID: "timer.test1", CONF_DURATION: -20},
            blocking=True,
        )

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CHANGE,
        {CONF_ENTITY_ID: "timer.test1", CONF_DURATION: -3},
        blocking=True,
    )
    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_ACTIVE
    assert state.attributes == {
        ATTR_EDITABLE: False,
        ATTR_DURATION: "0:00:15",
        ATTR_FINISHES_AT: (utcnow() + timedelta(seconds=12)).isoformat(),
        ATTR_LAST_ACTION: "started",  # Change does not set last_action
        ATTR_REMAINING: "0:00:12",
    }

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CHANGE,
        {CONF_ENTITY_ID: "timer.test1", CONF_DURATION: 2},
        blocking=True,
    )
    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_ACTIVE
    assert state.attributes == {
        ATTR_EDITABLE: False,
        ATTR_DURATION: "0:00:15",
        ATTR_FINISHES_AT: (utcnow() + timedelta(seconds=14)).isoformat(),
        ATTR_LAST_ACTION: "started",  # Change does not set last_action
        ATTR_REMAINING: "0:00:14",
    }

    await hass.services.async_call(
        DOMAIN, SERVICE_CANCEL, {CONF_ENTITY_ID: "timer.test1"}, blocking=True
    )
    await hass.async_block_till_done()
    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_IDLE
    assert state.attributes == {
        ATTR_EDITABLE: False,
        ATTR_DURATION: "0:00:10",
        ATTR_LAST_ACTION: "cancelled",
    }

    with pytest.raises(
        HomeAssistantError,
        match="Timer timer.test1 is not running, only active timers can be changed",
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CHANGE,
            {CONF_ENTITY_ID: "timer.test1", CONF_DURATION: 2},
            blocking=True,
        )

    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_IDLE
    assert state.attributes == {
        ATTR_EDITABLE: False,
        ATTR_DURATION: "0:00:10",
        ATTR_LAST_ACTION: "cancelled",  # Change does not set last_action
    }


@pytest.mark.freeze_time("2023-06-05 17:47:50")
async def test_wait_till_timer_expires(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test for a timer to end."""
    hass.set_state(CoreState.starting)

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"test1": {CONF_DURATION: 20}}})

    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_IDLE
    assert state.attributes == {
        ATTR_DURATION: "0:00:20",
        ATTR_EDITABLE: False,
        ATTR_LAST_ACTION: None,
    }

    results = []

    @callback
    def fake_event_listener(event):
        """Fake event listener for trigger."""
        results.append(event)

    hass.bus.async_listen(EVENT_TIMER_STARTED, fake_event_listener)
    hass.bus.async_listen(EVENT_TIMER_PAUSED, fake_event_listener)
    hass.bus.async_listen(EVENT_TIMER_FINISHED, fake_event_listener)
    hass.bus.async_listen(EVENT_TIMER_CANCELLED, fake_event_listener)
    hass.bus.async_listen(EVENT_TIMER_CHANGED, fake_event_listener)

    await hass.services.async_call(
        DOMAIN, SERVICE_START, {CONF_ENTITY_ID: "timer.test1"}, blocking=True
    )
    await hass.async_block_till_done()

    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_ACTIVE
    assert state.attributes == {
        ATTR_DURATION: "0:00:20",
        ATTR_EDITABLE: False,
        ATTR_FINISHES_AT: (utcnow() + timedelta(seconds=20)).isoformat(),
        ATTR_LAST_ACTION: "started",
        ATTR_REMAINING: "0:00:20",
    }

    assert results[-1].event_type == EVENT_TIMER_STARTED
    assert len(results) == 1

    await hass.services.async_call(
        DOMAIN,
        SERVICE_CHANGE,
        {CONF_ENTITY_ID: "timer.test1", CONF_DURATION: -5},
        blocking=True,
    )
    await hass.async_block_till_done()

    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_ACTIVE
    assert state.attributes == {
        ATTR_DURATION: "0:00:20",
        ATTR_EDITABLE: False,
        ATTR_FINISHES_AT: (utcnow() + timedelta(seconds=15)).isoformat(),
        ATTR_LAST_ACTION: "started",
        ATTR_REMAINING: "0:00:15",
    }

    assert results[-1].event_type == EVENT_TIMER_CHANGED
    assert len(results) == 2

    freezer.tick(10)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_ACTIVE
    assert state.attributes == {
        ATTR_DURATION: "0:00:20",
        ATTR_EDITABLE: False,
        ATTR_FINISHES_AT: (utcnow() + timedelta(seconds=5)).isoformat(),
        ATTR_LAST_ACTION: "started",
        ATTR_REMAINING: "0:00:15",
    }

    freezer.tick(20)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_IDLE
    assert state.attributes == {
        ATTR_DURATION: "0:00:20",
        ATTR_EDITABLE: False,
        ATTR_LAST_ACTION: "finished",
    }

    assert results[-1].event_type == EVENT_TIMER_FINISHED
    assert len(results) == 3


async def test_no_initial_state_and_no_restore_state(hass: HomeAssistant) -> None:
    """Ensure that entity is create without initial and restore feature."""
    hass.set_state(CoreState.starting)

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"test1": {CONF_DURATION: 10}}})

    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_IDLE
    assert state.attributes == {
        ATTR_DURATION: "0:00:10",
        ATTR_EDITABLE: False,
        ATTR_LAST_ACTION: None,
    }


async def test_config_reload(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_admin_user: MockUser,
    hass_read_only_user: MockUser,
) -> None:
    """Test reload service."""
    count_start = len(hass.states.async_entity_ids())

    _LOGGER.debug("ENTITIES @ start: %s", hass.states.async_entity_ids())

    config = {
        DOMAIN: {
            "test_1": {},
            "test_2": {
                CONF_NAME: "Hello World",
                CONF_ICON: "mdi:work",
                CONF_DURATION: 10,
            },
        }
    }

    assert await async_setup_component(hass, "timer", config)
    await hass.async_block_till_done()

    assert count_start + 2 == len(hass.states.async_entity_ids())
    await hass.async_block_till_done()

    state_1 = hass.states.get("timer.test_1")
    state_2 = hass.states.get("timer.test_2")
    state_3 = hass.states.get("timer.test_3")

    assert state_1 is not None
    assert state_2 is not None
    assert state_3 is None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_1") is not None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_2") is not None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_3") is None

    assert state_1.state == STATUS_IDLE
    assert state_1.attributes == {
        ATTR_DURATION: "0:00:00",
        ATTR_EDITABLE: False,
        ATTR_LAST_ACTION: None,
    }

    assert state_2.state == STATUS_IDLE
    assert state_2.attributes == {
        ATTR_DURATION: "0:00:10",
        ATTR_EDITABLE: False,
        ATTR_FRIENDLY_NAME: "Hello World",
        ATTR_ICON: "mdi:work",
        ATTR_LAST_ACTION: None,
    }

    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={
            DOMAIN: {
                "test_2": {
                    CONF_NAME: "Hello World reloaded",
                    CONF_ICON: "mdi:work-reloaded",
                    CONF_DURATION: 20,
                },
                "test_3": {},
            }
        },
    ):
        with pytest.raises(Unauthorized):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RELOAD,
                blocking=True,
                context=Context(user_id=hass_read_only_user.id),
            )
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await hass.async_block_till_done()

    assert count_start + 2 == len(hass.states.async_entity_ids())

    state_1 = hass.states.get("timer.test_1")
    state_2 = hass.states.get("timer.test_2")
    state_3 = hass.states.get("timer.test_3")

    assert state_1 is None
    assert state_2 is not None
    assert state_3 is not None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_1") is None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_2") is not None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, "test_3") is not None

    assert state_2.state == STATUS_IDLE
    assert state_2.attributes == {
        ATTR_DURATION: "0:00:20",
        ATTR_EDITABLE: False,
        ATTR_FRIENDLY_NAME: "Hello World reloaded",
        ATTR_ICON: "mdi:work-reloaded",
        ATTR_LAST_ACTION: None,
    }

    assert state_3.state == STATUS_IDLE
    assert state_3.attributes == {
        ATTR_DURATION: "0:00:00",
        ATTR_EDITABLE: False,
        ATTR_LAST_ACTION: None,
    }


@pytest.mark.freeze_time("2023-06-05 17:47:50")
async def test_timer_restarted_event(hass: HomeAssistant) -> None:
    """Ensure restarted event is called after starting a paused or running timer."""
    hass.set_state(CoreState.starting)

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"test1": {CONF_DURATION: 10}}})

    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_IDLE
    assert state.attributes == {
        ATTR_DURATION: "0:00:10",
        ATTR_EDITABLE: False,
        ATTR_LAST_ACTION: None,
    }

    results = []

    @callback
    def fake_event_listener(event):
        """Fake event listener for trigger."""
        results.append(event)

    hass.bus.async_listen(EVENT_TIMER_STARTED, fake_event_listener)
    hass.bus.async_listen(EVENT_TIMER_RESTARTED, fake_event_listener)
    hass.bus.async_listen(EVENT_TIMER_PAUSED, fake_event_listener)
    hass.bus.async_listen(EVENT_TIMER_FINISHED, fake_event_listener)
    hass.bus.async_listen(EVENT_TIMER_CANCELLED, fake_event_listener)

    await hass.services.async_call(
        DOMAIN, SERVICE_START, {CONF_ENTITY_ID: "timer.test1"}
    )
    await hass.async_block_till_done()
    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_ACTIVE
    assert state.attributes == {
        ATTR_DURATION: "0:00:10",
        ATTR_EDITABLE: False,
        ATTR_FINISHES_AT: (utcnow() + timedelta(seconds=10)).isoformat(),
        ATTR_LAST_ACTION: "started",
        ATTR_REMAINING: "0:00:10",
    }

    assert results[-1].event_type == EVENT_TIMER_STARTED
    assert len(results) == 1

    await hass.services.async_call(
        DOMAIN, SERVICE_START, {CONF_ENTITY_ID: "timer.test1"}
    )
    await hass.async_block_till_done()
    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_ACTIVE
    assert state.attributes == {
        ATTR_DURATION: "0:00:10",
        ATTR_EDITABLE: False,
        ATTR_FINISHES_AT: (utcnow() + timedelta(seconds=10)).isoformat(),
        ATTR_LAST_ACTION: "restarted",
        ATTR_REMAINING: "0:00:10",
    }

    assert results[-1].event_type == EVENT_TIMER_RESTARTED
    assert len(results) == 2

    await hass.services.async_call(
        DOMAIN, SERVICE_PAUSE, {CONF_ENTITY_ID: "timer.test1"}
    )
    await hass.async_block_till_done()
    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_PAUSED
    assert state.attributes == {
        ATTR_DURATION: "0:00:10",
        ATTR_EDITABLE: False,
        ATTR_LAST_ACTION: "paused",
        ATTR_REMAINING: "0:00:10",
    }

    assert results[-1].event_type == EVENT_TIMER_PAUSED
    assert len(results) == 3

    await hass.services.async_call(
        DOMAIN, SERVICE_START, {CONF_ENTITY_ID: "timer.test1"}
    )
    await hass.async_block_till_done()
    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_ACTIVE
    assert state.attributes == {
        ATTR_DURATION: "0:00:10",
        ATTR_EDITABLE: False,
        ATTR_FINISHES_AT: (utcnow() + timedelta(seconds=10)).isoformat(),
        ATTR_LAST_ACTION: "restarted",
        ATTR_REMAINING: "0:00:10",
    }

    assert results[-1].event_type == EVENT_TIMER_RESTARTED
    assert len(results) == 4


@pytest.mark.freeze_time("2023-06-05 17:47:50")
async def test_state_changed_when_timer_restarted(hass: HomeAssistant) -> None:
    """Ensure timer's state changes when it restarted."""
    hass.set_state(CoreState.starting)

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"test1": {CONF_DURATION: 10}}})

    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_IDLE
    assert state.attributes == {
        ATTR_DURATION: "0:00:10",
        ATTR_EDITABLE: False,
        ATTR_LAST_ACTION: None,
    }

    results = []

    @callback
    def fake_event_listener(event):
        """Fake event listener for trigger."""
        results.append(event)

    hass.bus.async_listen(EVENT_STATE_CHANGED, fake_event_listener)

    await hass.services.async_call(
        DOMAIN, SERVICE_START, {CONF_ENTITY_ID: "timer.test1"}
    )
    await hass.async_block_till_done()
    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_ACTIVE
    assert state.attributes == {
        ATTR_DURATION: "0:00:10",
        ATTR_EDITABLE: False,
        ATTR_FINISHES_AT: (utcnow() + timedelta(seconds=10)).isoformat(),
        ATTR_LAST_ACTION: "started",
        ATTR_REMAINING: "0:00:10",
    }

    assert results[-1].event_type == EVENT_STATE_CHANGED
    assert len(results) == 1

    await hass.services.async_call(
        DOMAIN, SERVICE_START, {CONF_ENTITY_ID: "timer.test1"}
    )
    await hass.async_block_till_done()
    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_ACTIVE
    assert state.attributes == {
        ATTR_DURATION: "0:00:10",
        ATTR_EDITABLE: False,
        ATTR_FINISHES_AT: (utcnow() + timedelta(seconds=10)).isoformat(),
        ATTR_LAST_ACTION: "restarted",
        ATTR_REMAINING: "0:00:10",
    }

    assert results[-1].event_type == EVENT_STATE_CHANGED
    assert len(results) == 2


@pytest.mark.freeze_time("2023-06-05 17:47:50")
async def test_last_action_after_restarted_timer_expires(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test that last_action changes from restarted to finished when timer expires."""
    hass.set_state(CoreState.starting)

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"test1": {CONF_DURATION: 10}}})

    # Start the timer
    await hass.services.async_call(
        DOMAIN, SERVICE_START, {CONF_ENTITY_ID: "timer.test1"}, blocking=True
    )
    await hass.async_block_till_done()

    # Restart the timer
    await hass.services.async_call(
        DOMAIN, SERVICE_START, {CONF_ENTITY_ID: "timer.test1"}, blocking=True
    )
    await hass.async_block_till_done()

    state = hass.states.get("timer.test1")
    assert state.state == STATUS_ACTIVE
    assert state.attributes[ATTR_LAST_ACTION] == "restarted"

    # Let the timer expire
    freezer.tick(15)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get("timer.test1")
    assert state.state == STATUS_IDLE
    assert state.attributes[ATTR_LAST_ACTION] == "finished"


@pytest.mark.freeze_time("2023-06-05 17:47:50")
async def test_last_action_persists_across_config_update(
    hass: HomeAssistant,
) -> None:
    """Test that last_action is preserved when the timer config is updated."""
    hass.set_state(CoreState.starting)

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"test1": {CONF_DURATION: 10}}})

    # Start and cancel to set last_action to "cancelled"
    await hass.services.async_call(
        DOMAIN, SERVICE_START, {CONF_ENTITY_ID: "timer.test1"}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN, SERVICE_CANCEL, {CONF_ENTITY_ID: "timer.test1"}, blocking=True
    )
    await hass.async_block_till_done()

    state = hass.states.get("timer.test1")
    assert state.state == STATUS_IDLE
    assert state.attributes[ATTR_LAST_ACTION] == "cancelled"

    # Reload with a new duration — last_action should persist
    with patch(
        "homeassistant.config.load_yaml_config_file",
        autospec=True,
        return_value={DOMAIN: {"test1": {CONF_DURATION: 20}}},
    ):
        await hass.services.async_call(DOMAIN, SERVICE_RELOAD, blocking=True)
        await hass.async_block_till_done()

    state = hass.states.get("timer.test1")
    assert state.state == STATUS_IDLE
    assert state.attributes[ATTR_DURATION] == "0:00:20"
    assert state.attributes[ATTR_LAST_ACTION] == "cancelled"


async def test_load_from_storage(hass: HomeAssistant, storage_setup) -> None:
    """Test set up from storage."""
    assert await storage_setup()
    state = hass.states.get(f"{DOMAIN}.timer_from_storage")
    assert state.state == STATUS_IDLE
    assert state.attributes == {
        ATTR_DURATION: "0:00:00",
        ATTR_EDITABLE: True,
        ATTR_FRIENDLY_NAME: "timer from storage",
        ATTR_LAST_ACTION: None,
    }


async def test_editable_state_attribute(hass: HomeAssistant, storage_setup) -> None:
    """Test editable attribute."""
    assert await storage_setup(config={DOMAIN: {"from_yaml": None}})

    state = hass.states.get(f"{DOMAIN}.{DOMAIN}_from_storage")
    assert state.state == STATUS_IDLE
    assert state.attributes == {
        ATTR_DURATION: "0:00:00",
        ATTR_EDITABLE: True,
        ATTR_FRIENDLY_NAME: "timer from storage",
        ATTR_LAST_ACTION: None,
    }

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert state.state == STATUS_IDLE
    assert state.attributes == {
        ATTR_DURATION: "0:00:00",
        ATTR_EDITABLE: False,
        ATTR_LAST_ACTION: None,
    }


async def test_ws_list(
    hass: HomeAssistant, hass_ws_client: WebSocketGenerator, storage_setup
) -> None:
    """Test listing via WS."""
    assert await storage_setup(config={DOMAIN: {"from_yaml": None}})

    client = await hass_ws_client(hass)

    await client.send_json({"id": 6, "type": f"{DOMAIN}/list"})
    resp = await client.receive_json()
    assert resp["success"]

    storage_ent = "from_storage"
    yaml_ent = "from_yaml"
    result = {item["id"]: item for item in resp["result"]}

    assert len(result) == 1
    assert storage_ent in result
    assert yaml_ent not in result
    assert result[storage_ent][ATTR_NAME] == "timer from storage"


async def test_ws_delete(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    storage_setup,
) -> None:
    """Test WS delete cleans up entity registry."""
    assert await storage_setup()

    timer_id = "from_storage"
    timer_entity_id = f"{DOMAIN}.{DOMAIN}_{timer_id}"

    state = hass.states.get(timer_entity_id)
    assert state is not None
    from_reg = entity_registry.async_get_entity_id(DOMAIN, DOMAIN, timer_id)
    assert from_reg == timer_entity_id

    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 6, "type": f"{DOMAIN}/delete", f"{DOMAIN}_id": f"{timer_id}"}
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(timer_entity_id)
    assert state is None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, timer_id) is None


async def test_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    storage_setup,
) -> None:
    """Test updating timer entity."""

    assert await storage_setup()

    timer_id = "from_storage"
    timer_entity_id = f"{DOMAIN}.{DOMAIN}_{timer_id}"

    state = hass.states.get(timer_entity_id)
    assert state.state == STATUS_IDLE
    assert state.attributes == {
        ATTR_DURATION: "0:00:00",
        ATTR_EDITABLE: True,
        ATTR_FRIENDLY_NAME: "timer from storage",
        ATTR_LAST_ACTION: None,
    }
    assert (
        entity_registry.async_get_entity_id(DOMAIN, DOMAIN, timer_id) == timer_entity_id
    )

    client = await hass_ws_client(hass)

    updated_settings = {
        CONF_NAME: "timer from storage",
        CONF_DURATION: 33,
        CONF_RESTORE: True,
    }
    await client.send_json(
        {
            "id": 6,
            "type": f"{DOMAIN}/update",
            f"{DOMAIN}_id": f"{timer_id}",
            **updated_settings,
        }
    )
    resp = await client.receive_json()
    assert resp["success"]
    assert resp["result"] == {
        "id": "from_storage",
        CONF_DURATION: "0:00:33",
        CONF_NAME: "timer from storage",
        CONF_RESTORE: True,
    }

    state = hass.states.get(timer_entity_id)
    assert state.state == STATUS_IDLE
    assert state.attributes == {
        ATTR_DURATION: "0:00:33",
        ATTR_EDITABLE: True,
        ATTR_FRIENDLY_NAME: "timer from storage",
        ATTR_LAST_ACTION: None,
        ATTR_RESTORE: True,
    }


async def test_ws_create(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    hass_ws_client: WebSocketGenerator,
    storage_setup,
) -> None:
    """Test create WS."""
    assert await storage_setup(items=[])

    timer_id = "new_timer"
    timer_entity_id = f"{DOMAIN}.{timer_id}"

    state = hass.states.get(timer_entity_id)
    assert state is None
    assert entity_registry.async_get_entity_id(DOMAIN, DOMAIN, timer_id) is None

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 6,
            "type": f"{DOMAIN}/create",
            CONF_NAME: "New Timer",
            CONF_DURATION: 42,
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(timer_entity_id)
    assert state.state == STATUS_IDLE
    assert state.attributes == {
        ATTR_DURATION: "0:00:42",
        ATTR_EDITABLE: True,
        ATTR_FRIENDLY_NAME: "New Timer",
        ATTR_LAST_ACTION: None,
    }
    assert (
        entity_registry.async_get_entity_id(DOMAIN, DOMAIN, timer_id) == timer_entity_id
    )


async def test_setup_no_config(hass: HomeAssistant, hass_admin_user: MockUser) -> None:
    """Test component setup with no config."""
    count_start = len(hass.states.async_entity_ids())
    assert await async_setup_component(hass, DOMAIN, {})

    with patch(
        "homeassistant.config.load_yaml_config_file", autospec=True, return_value={}
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RELOAD,
            blocking=True,
            context=Context(user_id=hass_admin_user.id),
        )
        await hass.async_block_till_done()

    assert count_start == len(hass.states.async_entity_ids())


@pytest.mark.parametrize("last_action", [None, "cancelled", "finished"])
async def test_restore_idle(hass: HomeAssistant, last_action: str | None) -> None:
    """Test entity restore logic when timer is idle."""
    utc_now = utcnow()
    attrs: dict[str, Any] = {ATTR_DURATION: "0:00:30"}
    if last_action is not None:
        attrs[ATTR_LAST_ACTION] = last_action
    stored_state = StoredState(
        State("timer.test", STATUS_IDLE, attrs),
        None,
        utc_now,
    )

    data = async_get(hass)
    await data.store.async_save([stored_state.as_dict()])
    await data.async_load()

    entity = Timer.from_storage(
        {
            CONF_ID: "test",
            CONF_NAME: "test",
            CONF_DURATION: "0:01:00",
            CONF_RESTORE: True,
        }
    )
    entity.hass = hass
    entity.entity_id = "timer.test"

    await entity.async_added_to_hass()
    await hass.async_block_till_done()
    assert entity.state == STATUS_IDLE
    assert entity.extra_state_attributes == {
        # Idle timers reset to the configured duration, not the stored one
        ATTR_DURATION: "0:01:00",
        ATTR_EDITABLE: True,
        ATTR_LAST_ACTION: last_action,
        ATTR_RESTORE: True,
    }


@pytest.mark.freeze_time("2023-06-05 17:47:50")
async def test_restore_paused(hass: HomeAssistant) -> None:
    """Test entity restore logic when timer is paused."""
    utc_now = utcnow()
    stored_state = StoredState(
        State(
            "timer.test",
            STATUS_PAUSED,
            {
                ATTR_DURATION: "0:00:30",
                ATTR_LAST_ACTION: "paused",
                ATTR_REMAINING: "0:00:15",
            },
        ),
        None,
        utc_now,
    )

    data = async_get(hass)
    await data.store.async_save([stored_state.as_dict()])
    await data.async_load()

    entity = Timer.from_storage(
        {
            CONF_ID: "test",
            CONF_NAME: "test",
            CONF_DURATION: "0:01:00",
            CONF_RESTORE: True,
        }
    )
    entity.hass = hass
    entity.entity_id = "timer.test"

    await entity.async_added_to_hass()
    await hass.async_block_till_done()
    assert entity.state == STATUS_PAUSED
    assert entity.extra_state_attributes == {
        ATTR_DURATION: "0:00:30",
        ATTR_EDITABLE: True,
        ATTR_LAST_ACTION: "paused",
        ATTR_REMAINING: "0:00:15",
        ATTR_RESTORE: True,
    }


@pytest.mark.freeze_time("2023-06-05 17:47:50")
@pytest.mark.parametrize("last_action", [None, "started", "restarted"])
async def test_restore_active_resume(
    hass: HomeAssistant, last_action: str | None
) -> None:
    """Test entity restore logic when timer is active and end time is after startup."""
    events = async_capture_events(hass, EVENT_TIMER_RESTARTED)
    assert not events
    utc_now = utcnow()
    finish = utc_now + timedelta(seconds=30)
    simulated_utc_now = utc_now + timedelta(seconds=15)
    stored_state = StoredState(
        State(
            "timer.test",
            STATUS_ACTIVE,
            {
                ATTR_DURATION: "0:00:30",
                ATTR_FINISHES_AT: finish.isoformat(),
                ATTR_LAST_ACTION: last_action,
            },
        ),
        None,
        utc_now,
    )

    data = async_get(hass)
    await data.store.async_save([stored_state.as_dict()])
    await data.async_load()

    entity = Timer.from_storage(
        {
            CONF_ID: "test",
            CONF_NAME: "test",
            CONF_DURATION: "0:01:00",
            CONF_RESTORE: True,
        }
    )
    entity.hass = hass
    entity.entity_id = "timer.test"

    # In patch make sure we ignore microseconds
    with patch(
        "homeassistant.components.timer.dt_util.utcnow",
        return_value=simulated_utc_now.replace(microsecond=999),
    ):
        await entity.async_added_to_hass()
        await hass.async_block_till_done()

    assert entity.state == STATUS_ACTIVE
    assert entity.extra_state_attributes == {
        ATTR_DURATION: "0:00:30",
        ATTR_EDITABLE: True,
        ATTR_FINISHES_AT: finish.isoformat(),
        ATTR_LAST_ACTION: "restarted",
        ATTR_REMAINING: "0:00:15",
        ATTR_RESTORE: True,
    }
    assert len(events) == 1


@pytest.mark.parametrize("last_action", [None, "started", "restarted"])
async def test_restore_active_finished_outside_grace(
    hass: HomeAssistant, last_action: str | None
) -> None:
    """Test entity restore logic: timer is active, ended while Home Assistant was stopped."""
    events = async_capture_events(hass, EVENT_TIMER_FINISHED)
    assert not events
    utc_now = utcnow()
    finish = utc_now + timedelta(seconds=30)
    simulated_utc_now = utc_now + timedelta(seconds=46)
    stored_state = StoredState(
        State(
            "timer.test",
            STATUS_ACTIVE,
            {
                ATTR_DURATION: "0:00:30",
                ATTR_FINISHES_AT: finish.isoformat(),
                ATTR_LAST_ACTION: last_action,
            },
        ),
        None,
        utc_now,
    )

    data = async_get(hass)
    await data.store.async_save([stored_state.as_dict()])
    await data.async_load()

    entity = Timer.from_storage(
        {
            CONF_ID: "test",
            CONF_NAME: "test",
            CONF_DURATION: "0:01:00",
            CONF_RESTORE: True,
        }
    )
    entity.hass = hass
    entity.entity_id = "timer.test"

    with patch(
        "homeassistant.components.timer.dt_util.utcnow", return_value=simulated_utc_now
    ):
        await entity.async_added_to_hass()
        await hass.async_block_till_done()

    assert entity.state == STATUS_IDLE
    assert entity.extra_state_attributes == {
        ATTR_DURATION: "0:01:00",
        ATTR_EDITABLE: True,
        ATTR_LAST_ACTION: "finished",
        ATTR_RESTORE: True,
    }
    assert len(events) == 1
