"""The tests for the timer component."""
# pylint: disable=protected-access
from datetime import timedelta
import logging
from unittest.mock import patch

import pytest

from homeassistant.components.timer import (
    ATTR_DURATION,
    CONF_DURATION,
    CONF_ICON,
    CONF_NAME,
    DEFAULT_DURATION,
    DOMAIN,
    EVENT_TIMER_CANCELLED,
    EVENT_TIMER_FINISHED,
    EVENT_TIMER_PAUSED,
    EVENT_TIMER_RESTARTED,
    EVENT_TIMER_STARTED,
    SERVICE_CANCEL,
    SERVICE_FINISH,
    SERVICE_PAUSE,
    SERVICE_START,
    STATUS_ACTIVE,
    STATUS_IDLE,
    STATUS_PAUSED,
    _format_timedelta,
)
from homeassistant.const import (
    ATTR_EDITABLE,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    ATTR_ID,
    ATTR_NAME,
    CONF_ENTITY_ID,
    EVENT_STATE_CHANGED,
    SERVICE_RELOAD,
)
from homeassistant.core import Context, CoreState
from homeassistant.exceptions import Unauthorized
from homeassistant.helpers import config_validation as cv, entity_registry
from homeassistant.setup import async_setup_component
from homeassistant.util.dt import utcnow

from tests.common import async_fire_time_changed

_LOGGER = logging.getLogger(__name__)


@pytest.fixture
def storage_setup(hass, hass_storage):
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


async def test_config(hass):
    """Test config."""
    invalid_configs = [None, 1, {}, {"name with space": None}]

    for cfg in invalid_configs:
        assert not await async_setup_component(hass, DOMAIN, {DOMAIN: cfg})


async def test_config_options(hass):
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

    assert STATUS_IDLE == state_1.state
    assert ATTR_ICON not in state_1.attributes
    assert ATTR_FRIENDLY_NAME not in state_1.attributes

    assert STATUS_IDLE == state_2.state
    assert "Hello World" == state_2.attributes.get(ATTR_FRIENDLY_NAME)
    assert "mdi:work" == state_2.attributes.get(ATTR_ICON)
    assert "0:00:10" == state_2.attributes.get(ATTR_DURATION)

    assert STATUS_IDLE == state_3.state
    assert str(cv.time_period(DEFAULT_DURATION)) == state_3.attributes.get(
        CONF_DURATION
    )


async def test_methods_and_events(hass):
    """Test methods and events."""
    hass.state = CoreState.starting

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"test1": {CONF_DURATION: 10}}})

    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_IDLE

    results = []

    def fake_event_listener(event):
        """Fake event listener for trigger."""
        results.append(event)

    hass.bus.async_listen(EVENT_TIMER_STARTED, fake_event_listener)
    hass.bus.async_listen(EVENT_TIMER_RESTARTED, fake_event_listener)
    hass.bus.async_listen(EVENT_TIMER_PAUSED, fake_event_listener)
    hass.bus.async_listen(EVENT_TIMER_FINISHED, fake_event_listener)
    hass.bus.async_listen(EVENT_TIMER_CANCELLED, fake_event_listener)

    steps = [
        {"call": SERVICE_START, "state": STATUS_ACTIVE, "event": EVENT_TIMER_STARTED},
        {"call": SERVICE_PAUSE, "state": STATUS_PAUSED, "event": EVENT_TIMER_PAUSED},
        {"call": SERVICE_START, "state": STATUS_ACTIVE, "event": EVENT_TIMER_RESTARTED},
        {"call": SERVICE_CANCEL, "state": STATUS_IDLE, "event": EVENT_TIMER_CANCELLED},
        {"call": SERVICE_START, "state": STATUS_ACTIVE, "event": EVENT_TIMER_STARTED},
        {"call": SERVICE_FINISH, "state": STATUS_IDLE, "event": EVENT_TIMER_FINISHED},
        {"call": SERVICE_START, "state": STATUS_ACTIVE, "event": EVENT_TIMER_STARTED},
        {"call": SERVICE_PAUSE, "state": STATUS_PAUSED, "event": EVENT_TIMER_PAUSED},
        {"call": SERVICE_CANCEL, "state": STATUS_IDLE, "event": EVENT_TIMER_CANCELLED},
        {"call": SERVICE_START, "state": STATUS_ACTIVE, "event": EVENT_TIMER_STARTED},
        {"call": SERVICE_START, "state": STATUS_ACTIVE, "event": EVENT_TIMER_RESTARTED},
    ]

    expectedEvents = 0
    for step in steps:
        if step["call"] is not None:
            await hass.services.async_call(
                DOMAIN, step["call"], {CONF_ENTITY_ID: "timer.test1"}
            )
            await hass.async_block_till_done()

        state = hass.states.get("timer.test1")
        assert state
        if step["state"] is not None:
            assert state.state == step["state"]

        if step["event"] is not None:
            expectedEvents += 1
            assert results[-1].event_type == step["event"]
            assert len(results) == expectedEvents


async def test_wait_till_timer_expires(hass):
    """Test for a timer to end."""
    hass.state = CoreState.starting

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"test1": {CONF_DURATION: 10}}})

    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_IDLE

    results = []

    def fake_event_listener(event):
        """Fake event listener for trigger."""
        results.append(event)

    hass.bus.async_listen(EVENT_TIMER_STARTED, fake_event_listener)
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

    assert results[-1].event_type == EVENT_TIMER_STARTED
    assert len(results) == 1

    async_fire_time_changed(hass, utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()

    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_IDLE

    assert results[-1].event_type == EVENT_TIMER_FINISHED
    assert len(results) == 2


async def test_no_initial_state_and_no_restore_state(hass):
    """Ensure that entity is create without initial and restore feature."""
    hass.state = CoreState.starting

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"test1": {CONF_DURATION: 10}}})

    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_IDLE


async def test_config_reload(hass, hass_admin_user, hass_read_only_user):
    """Test reload service."""
    count_start = len(hass.states.async_entity_ids())
    ent_reg = await entity_registry.async_get_registry(hass)

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
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "test_1") is not None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "test_2") is not None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "test_3") is None

    assert STATUS_IDLE == state_1.state
    assert ATTR_ICON not in state_1.attributes
    assert ATTR_FRIENDLY_NAME not in state_1.attributes

    assert STATUS_IDLE == state_2.state
    assert "Hello World" == state_2.attributes.get(ATTR_FRIENDLY_NAME)
    assert "mdi:work" == state_2.attributes.get(ATTR_ICON)
    assert "0:00:10" == state_2.attributes.get(ATTR_DURATION)

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
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "test_1") is None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "test_2") is not None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, "test_3") is not None

    assert STATUS_IDLE == state_2.state
    assert "Hello World reloaded" == state_2.attributes.get(ATTR_FRIENDLY_NAME)
    assert "mdi:work-reloaded" == state_2.attributes.get(ATTR_ICON)
    assert "0:00:20" == state_2.attributes.get(ATTR_DURATION)

    assert STATUS_IDLE == state_3.state
    assert ATTR_ICON not in state_3.attributes
    assert ATTR_FRIENDLY_NAME not in state_3.attributes


async def test_timer_restarted_event(hass):
    """Ensure restarted event is called after starting a paused or running timer."""
    hass.state = CoreState.starting

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"test1": {CONF_DURATION: 10}}})

    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_IDLE

    results = []

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

    assert results[-1].event_type == EVENT_TIMER_STARTED
    assert len(results) == 1

    await hass.services.async_call(
        DOMAIN, SERVICE_START, {CONF_ENTITY_ID: "timer.test1"}
    )
    await hass.async_block_till_done()
    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_ACTIVE

    assert results[-1].event_type == EVENT_TIMER_RESTARTED
    assert len(results) == 2

    await hass.services.async_call(
        DOMAIN, SERVICE_PAUSE, {CONF_ENTITY_ID: "timer.test1"}
    )
    await hass.async_block_till_done()
    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_PAUSED

    assert results[-1].event_type == EVENT_TIMER_PAUSED
    assert len(results) == 3

    await hass.services.async_call(
        DOMAIN, SERVICE_START, {CONF_ENTITY_ID: "timer.test1"}
    )
    await hass.async_block_till_done()
    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_ACTIVE

    assert results[-1].event_type == EVENT_TIMER_RESTARTED
    assert len(results) == 4


async def test_state_changed_when_timer_restarted(hass):
    """Ensure timer's state changes when it restarted."""
    hass.state = CoreState.starting

    await async_setup_component(hass, DOMAIN, {DOMAIN: {"test1": {CONF_DURATION: 10}}})

    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_IDLE

    results = []

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

    assert results[-1].event_type == EVENT_STATE_CHANGED
    assert len(results) == 1

    await hass.services.async_call(
        DOMAIN, SERVICE_START, {CONF_ENTITY_ID: "timer.test1"}
    )
    await hass.async_block_till_done()
    state = hass.states.get("timer.test1")
    assert state
    assert state.state == STATUS_ACTIVE

    assert results[-1].event_type == EVENT_STATE_CHANGED
    assert len(results) == 2


async def test_load_from_storage(hass, storage_setup):
    """Test set up from storage."""
    assert await storage_setup()
    state = hass.states.get(f"{DOMAIN}.timer_from_storage")
    assert state.state == STATUS_IDLE
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "timer from storage"
    assert state.attributes.get(ATTR_EDITABLE)


async def test_editable_state_attribute(hass, storage_setup):
    """Test editable attribute."""
    assert await storage_setup(config={DOMAIN: {"from_yaml": None}})

    state = hass.states.get(f"{DOMAIN}.{DOMAIN}_from_storage")
    assert state.state == STATUS_IDLE
    assert state.attributes.get(ATTR_FRIENDLY_NAME) == "timer from storage"
    assert state.attributes.get(ATTR_EDITABLE)

    state = hass.states.get(f"{DOMAIN}.from_yaml")
    assert not state.attributes.get(ATTR_EDITABLE)
    assert state.state == STATUS_IDLE


async def test_ws_list(hass, hass_ws_client, storage_setup):
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


async def test_ws_delete(hass, hass_ws_client, storage_setup):
    """Test WS delete cleans up entity registry."""
    assert await storage_setup()

    timer_id = "from_storage"
    timer_entity_id = f"{DOMAIN}.{DOMAIN}_{timer_id}"
    ent_reg = await entity_registry.async_get_registry(hass)

    state = hass.states.get(timer_entity_id)
    assert state is not None
    from_reg = ent_reg.async_get_entity_id(DOMAIN, DOMAIN, timer_id)
    assert from_reg == timer_entity_id

    client = await hass_ws_client(hass)

    await client.send_json(
        {"id": 6, "type": f"{DOMAIN}/delete", f"{DOMAIN}_id": f"{timer_id}"}
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(timer_entity_id)
    assert state is None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, timer_id) is None


async def test_update(hass, hass_ws_client, storage_setup):
    """Test updating timer entity."""

    assert await storage_setup()

    timer_id = "from_storage"
    timer_entity_id = f"{DOMAIN}.{DOMAIN}_{timer_id}"
    ent_reg = await entity_registry.async_get_registry(hass)

    state = hass.states.get(timer_entity_id)
    assert state.attributes[ATTR_FRIENDLY_NAME] == "timer from storage"
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, timer_id) == timer_entity_id

    client = await hass_ws_client(hass)

    await client.send_json(
        {
            "id": 6,
            "type": f"{DOMAIN}/update",
            f"{DOMAIN}_id": f"{timer_id}",
            CONF_DURATION: 33,
        }
    )
    resp = await client.receive_json()
    assert resp["success"]

    state = hass.states.get(timer_entity_id)
    assert state.attributes[ATTR_DURATION] == _format_timedelta(cv.time_period(33))


async def test_ws_create(hass, hass_ws_client, storage_setup):
    """Test create WS."""
    assert await storage_setup(items=[])

    timer_id = "new_timer"
    timer_entity_id = f"{DOMAIN}.{timer_id}"
    ent_reg = await entity_registry.async_get_registry(hass)

    state = hass.states.get(timer_entity_id)
    assert state is None
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, timer_id) is None

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
    assert state.attributes[ATTR_DURATION] == _format_timedelta(cv.time_period(42))
    assert ent_reg.async_get_entity_id(DOMAIN, DOMAIN, timer_id) == timer_entity_id


async def test_setup_no_config(hass, hass_admin_user):
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
