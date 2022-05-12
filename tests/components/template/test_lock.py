"""The tests for the Template lock platform."""
import pytest

from homeassistant import setup
from homeassistant.components import lock
from homeassistant.const import (
    ATTR_DOMAIN,
    ATTR_ENTITY_ID,
    ATTR_SERVICE_DATA,
    EVENT_CALL_SERVICE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import callback


@pytest.fixture
def service_calls(hass):
    """Track service call events for switch.test_state."""
    events = []
    entity_id = "switch.test_state"

    @callback
    def capture_events(event):
        if event.data[ATTR_DOMAIN] != "switch":
            return
        if event.data[ATTR_SERVICE_DATA][ATTR_ENTITY_ID] != [entity_id]:
            return
        events.append(event)

    hass.bus.async_listen(EVENT_CALL_SERVICE, capture_events)

    return events


OPTIMISTIC_LOCK_CONFIG = {
    "platform": "template",
    "lock": {
        "service": "switch.turn_on",
        "entity_id": "switch.test_state",
    },
    "unlock": {
        "service": "switch.turn_off",
        "entity_id": "switch.test_state",
    },
}


@pytest.mark.parametrize("count,domain", [(1, lock.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            lock.DOMAIN: {
                **OPTIMISTIC_LOCK_CONFIG,
                "name": "Test template lock",
                "value_template": "{{ states.switch.test_state.state }}",
            }
        },
    ],
)
async def test_template_state(hass, start_ha):
    """Test template."""
    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("lock.test_template_lock")
    assert state.state == lock.STATE_LOCKED

    hass.states.async_set("switch.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("lock.test_template_lock")
    assert state.state == lock.STATE_UNLOCKED


@pytest.mark.parametrize("count,domain", [(1, lock.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            lock.DOMAIN: {
                **OPTIMISTIC_LOCK_CONFIG,
                "value_template": "{{ 1 == 1 }}",
            }
        },
    ],
)
async def test_template_state_boolean_on(hass, start_ha):
    """Test the setting of the state with boolean on."""
    state = hass.states.get("lock.template_lock")
    assert state.state == lock.STATE_LOCKED


@pytest.mark.parametrize("count,domain", [(1, lock.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            lock.DOMAIN: {
                **OPTIMISTIC_LOCK_CONFIG,
                "value_template": "{{ 1 == 2 }}",
            }
        },
    ],
)
async def test_template_state_boolean_off(hass, start_ha):
    """Test the setting of the state with off."""
    state = hass.states.get("lock.template_lock")
    assert state.state == lock.STATE_UNLOCKED


@pytest.mark.parametrize("count,domain", [(0, lock.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            lock.DOMAIN: {
                "platform": "template",
                "value_template": "{% if rubbish %}",
                "lock": {
                    "service": "switch.turn_on",
                    "entity_id": "switch.test_state",
                },
                "unlock": {
                    "service": "switch.turn_off",
                    "entity_id": "switch.test_state",
                },
            }
        },
        {
            "switch": {
                "platform": "lock",
                "name": "{{%}",
                "value_template": "{{ rubbish }",
                "lock": {
                    "service": "switch.turn_on",
                    "entity_id": "switch.test_state",
                },
                "unlock": {
                    "service": "switch.turn_off",
                    "entity_id": "switch.test_state",
                },
            },
        },
        {lock.DOMAIN: {"platform": "template", "value_template": "Invalid"}},
        {
            lock.DOMAIN: {
                "platform": "template",
                "not_value_template": "{{ states.switch.test_state.state }}",
                "lock": {
                    "service": "switch.turn_on",
                    "entity_id": "switch.test_state",
                },
                "unlock": {
                    "service": "switch.turn_off",
                    "entity_id": "switch.test_state",
                },
            }
        },
    ],
)
async def test_template_syntax_error(hass, start_ha):
    """Test templating syntax error."""
    assert hass.states.async_all("lock") == []


@pytest.mark.parametrize("count,domain", [(1, lock.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            lock.DOMAIN: {
                **OPTIMISTIC_LOCK_CONFIG,
                "value_template": "{{ 1 + 1 }}",
            }
        },
    ],
)
async def test_template_static(hass, start_ha):
    """Test that we allow static templates."""
    state = hass.states.get("lock.template_lock")
    assert state.state == lock.STATE_UNLOCKED

    hass.states.async_set("lock.template_lock", lock.STATE_LOCKED)
    await hass.async_block_till_done()
    state = hass.states.get("lock.template_lock")
    assert state.state == lock.STATE_LOCKED


@pytest.mark.parametrize("count,domain", [(1, lock.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            lock.DOMAIN: {
                **OPTIMISTIC_LOCK_CONFIG,
                "value_template": "{{ states.switch.test_state.state }}",
            }
        },
    ],
)
async def test_lock_action(hass, start_ha, service_calls):
    """Test lock action."""
    await setup.async_setup_component(hass, "switch", {})
    hass.states.async_set("switch.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == lock.STATE_UNLOCKED

    await hass.services.async_call(
        lock.DOMAIN, lock.SERVICE_LOCK, {ATTR_ENTITY_ID: "lock.template_lock"}
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[-1].data["service"] == "turn_on"


@pytest.mark.parametrize("count,domain", [(1, lock.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            lock.DOMAIN: {
                **OPTIMISTIC_LOCK_CONFIG,
                "value_template": "{{ states.switch.test_state.state }}",
            }
        },
    ],
)
async def test_unlock_action(hass, start_ha, service_calls):
    """Test unlock action."""
    await setup.async_setup_component(hass, "switch", {})
    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == lock.STATE_LOCKED

    await hass.services.async_call(
        lock.DOMAIN, lock.SERVICE_UNLOCK, {ATTR_ENTITY_ID: "lock.template_lock"}
    )
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[-1].data["service"] == "turn_off"


@pytest.mark.parametrize("count,domain", [(1, lock.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            lock.DOMAIN: {
                **OPTIMISTIC_LOCK_CONFIG,
                "value_template": "{{ states.input_select.test_state.state }}",
            }
        },
    ],
)
@pytest.mark.parametrize(
    "test_state", [lock.STATE_UNLOCKING, lock.STATE_LOCKING, lock.STATE_JAMMED]
)
async def test_lock_state(hass, test_state, start_ha):
    """Test value template."""
    hass.states.async_set("input_select.test_state", test_state)
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == test_state


@pytest.mark.parametrize("count,domain", [(1, lock.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            lock.DOMAIN: {
                **OPTIMISTIC_LOCK_CONFIG,
                "value_template": "{{ states('switch.test_state') }}",
                "availability_template": "{{ is_state('availability_state.state', 'on') }}",
            }
        },
    ],
)
async def test_available_template_with_entities(hass, start_ha):
    """Test availability templates with values from other entities."""
    # When template returns true..
    hass.states.async_set("availability_state.state", STATE_ON)
    await hass.async_block_till_done()

    # Device State should not be unavailable
    assert hass.states.get("lock.template_lock").state != STATE_UNAVAILABLE

    # When Availability template returns false
    hass.states.async_set("availability_state.state", STATE_OFF)
    await hass.async_block_till_done()

    # device state should be unavailable
    assert hass.states.get("lock.template_lock").state == STATE_UNAVAILABLE


@pytest.mark.parametrize("count,domain", [(1, lock.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            lock.DOMAIN: {
                **OPTIMISTIC_LOCK_CONFIG,
                "value_template": "{{ 1 + 1 }}",
                "availability_template": "{{ x - 12 }}",
            }
        },
    ],
)
async def test_invalid_availability_template_keeps_component_available(
    hass, start_ha, caplog_setup_text
):
    """Test that an invalid availability keeps the device available."""
    assert hass.states.get("lock.template_lock").state != STATE_UNAVAILABLE
    assert ("UndefinedError: 'x' is undefined") in caplog_setup_text


@pytest.mark.parametrize("count,domain", [(1, lock.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            lock.DOMAIN: {
                **OPTIMISTIC_LOCK_CONFIG,
                "name": "test_template_lock_01",
                "unique_id": "not-so-unique-anymore",
                "value_template": "{{ true }}",
            }
        },
    ],
)
async def test_unique_id(hass, start_ha):
    """Test unique_id option only creates one lock per id."""
    await setup.async_setup_component(
        hass,
        lock.DOMAIN,
        {
            "lock": {
                **OPTIMISTIC_LOCK_CONFIG,
                "name": "test_template_lock_02",
                "unique_id": "not-so-unique-anymore",
                "value_template": "{{ false }}",
            },
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all("lock")) == 1
