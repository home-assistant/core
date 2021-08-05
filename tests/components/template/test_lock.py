"""The tests for the Template lock platform."""
import pytest

from homeassistant import setup
from homeassistant.components import lock
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, STATE_UNAVAILABLE

from tests.common import assert_setup_component, async_mock_service


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_template_state(hass):
    """Test template."""
    with assert_setup_component(1, lock.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            lock.DOMAIN,
            {
                "lock": {
                    "platform": "template",
                    "name": "Test template lock",
                    "value_template": "{{ states.switch.test_state.state }}",
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
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("lock.test_template_lock")
    assert state.state == lock.STATE_LOCKED

    hass.states.async_set("switch.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("lock.test_template_lock")
    assert state.state == lock.STATE_UNLOCKED


async def test_template_state_boolean_on(hass):
    """Test the setting of the state with boolean on."""
    with assert_setup_component(1, lock.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            lock.DOMAIN,
            {
                "lock": {
                    "platform": "template",
                    "value_template": "{{ 1 == 1 }}",
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
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == lock.STATE_LOCKED


async def test_template_state_boolean_off(hass):
    """Test the setting of the state with off."""
    with assert_setup_component(1, lock.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            lock.DOMAIN,
            {
                "lock": {
                    "platform": "template",
                    "value_template": "{{ 1 == 2 }}",
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
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == lock.STATE_UNLOCKED


async def test_template_syntax_error(hass):
    """Test templating syntax error."""
    with assert_setup_component(0, lock.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            lock.DOMAIN,
            {
                "lock": {
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
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_invalid_name_does_not_create(hass):
    """Test invalid name."""
    with assert_setup_component(0, lock.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            lock.DOMAIN,
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
                }
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_invalid_lock_does_not_create(hass):
    """Test invalid lock."""
    with assert_setup_component(0, lock.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            lock.DOMAIN,
            {"lock": {"platform": "template", "value_template": "Invalid"}},
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_missing_template_does_not_create(hass):
    """Test missing template."""
    with assert_setup_component(0, lock.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            lock.DOMAIN,
            {
                "lock": {
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
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.async_all() == []


async def test_template_static(hass, caplog):
    """Test that we allow static templates."""
    with assert_setup_component(1, lock.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            lock.DOMAIN,
            {
                "lock": {
                    "platform": "template",
                    "value_template": "{{ 1 + 1 }}",
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
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == lock.STATE_UNLOCKED

    hass.states.async_set("lock.template_lock", lock.STATE_LOCKED)
    await hass.async_block_till_done()
    state = hass.states.get("lock.template_lock")
    assert state.state == lock.STATE_LOCKED


async def test_lock_action(hass, calls):
    """Test lock action."""
    assert await setup.async_setup_component(
        hass,
        lock.DOMAIN,
        {
            "lock": {
                "platform": "template",
                "value_template": "{{ states.switch.test_state.state }}",
                "lock": {"service": "test.automation"},
                "unlock": {
                    "service": "switch.turn_off",
                    "entity_id": "switch.test_state",
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("switch.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == lock.STATE_UNLOCKED

    await hass.services.async_call(
        lock.DOMAIN, lock.SERVICE_LOCK, {ATTR_ENTITY_ID: "lock.template_lock"}
    )
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_unlock_action(hass, calls):
    """Test unlock action."""
    assert await setup.async_setup_component(
        hass,
        lock.DOMAIN,
        {
            "lock": {
                "platform": "template",
                "value_template": "{{ states.switch.test_state.state }}",
                "lock": {
                    "service": "switch.turn_on",
                    "entity_id": "switch.test_state",
                },
                "unlock": {"service": "test.automation"},
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == lock.STATE_LOCKED

    await hass.services.async_call(
        lock.DOMAIN, lock.SERVICE_UNLOCK, {ATTR_ENTITY_ID: "lock.template_lock"}
    )
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_unlocking(hass, calls):
    """Test unlocking."""
    assert await setup.async_setup_component(
        hass,
        lock.DOMAIN,
        {
            "lock": {
                "platform": "template",
                "value_template": "{{ states.input_select.test_state.state }}",
                "lock": {"service": "test.automation"},
                "unlock": {"service": "test.automation"},
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("input_select.test_state", lock.STATE_UNLOCKING)
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == lock.STATE_UNLOCKING


async def test_locking(hass, calls):
    """Test unlocking."""
    assert await setup.async_setup_component(
        hass,
        lock.DOMAIN,
        {
            "lock": {
                "platform": "template",
                "value_template": "{{ states.input_select.test_state.state }}",
                "lock": {"service": "test.automation"},
                "unlock": {"service": "test.automation"},
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("input_select.test_state", lock.STATE_LOCKING)
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == lock.STATE_LOCKING


async def test_jammed(hass, calls):
    """Test jammed."""
    assert await setup.async_setup_component(
        hass,
        lock.DOMAIN,
        {
            "lock": {
                "platform": "template",
                "value_template": "{{ states.input_select.test_state.state }}",
                "lock": {"service": "test.automation"},
                "unlock": {"service": "test.automation"},
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    hass.states.async_set("input_select.test_state", lock.STATE_JAMMED)
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == lock.STATE_JAMMED


async def test_available_template_with_entities(hass):
    """Test availability templates with values from other entities."""

    await setup.async_setup_component(
        hass,
        lock.DOMAIN,
        {
            "lock": {
                "platform": "template",
                "value_template": "{{ states('switch.test_state') }}",
                "lock": {"service": "switch.turn_on", "entity_id": "switch.test_state"},
                "unlock": {
                    "service": "switch.turn_off",
                    "entity_id": "switch.test_state",
                },
                "availability_template": "{{ is_state('availability_state.state', 'on') }}",
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

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


async def test_invalid_availability_template_keeps_component_available(hass, caplog):
    """Test that an invalid availability keeps the device available."""
    await setup.async_setup_component(
        hass,
        lock.DOMAIN,
        {
            "lock": {
                "platform": "template",
                "value_template": "{{ 1 + 1 }}",
                "availability_template": "{{ x - 12 }}",
                "lock": {"service": "switch.turn_on", "entity_id": "switch.test_state"},
                "unlock": {
                    "service": "switch.turn_off",
                    "entity_id": "switch.test_state",
                },
            }
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert hass.states.get("lock.template_lock").state != STATE_UNAVAILABLE
    assert ("UndefinedError: 'x' is undefined") in caplog.text


async def test_unique_id(hass):
    """Test unique_id option only creates one lock per id."""
    await setup.async_setup_component(
        hass,
        lock.DOMAIN,
        {
            "lock": {
                "platform": "template",
                "name": "test_template_lock_01",
                "unique_id": "not-so-unique-anymore",
                "value_template": "{{ true }}",
                "lock": {"service": "switch.turn_on", "entity_id": "switch.test_state"},
                "unlock": {
                    "service": "switch.turn_off",
                    "entity_id": "switch.test_state",
                },
            },
        },
    )

    await setup.async_setup_component(
        hass,
        lock.DOMAIN,
        {
            "lock": {
                "platform": "template",
                "name": "test_template_lock_02",
                "unique_id": "not-so-unique-anymore",
                "value_template": "{{ false }}",
                "lock": {"service": "switch.turn_on", "entity_id": "switch.test_state"},
                "unlock": {
                    "service": "switch.turn_off",
                    "entity_id": "switch.test_state",
                },
            },
        },
    )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 1
