"""The tests for the Template lock platform."""

import pytest

from homeassistant import setup
from homeassistant.components import lock
from homeassistant.components.lock import LockState
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant, ServiceCall

OPTIMISTIC_LOCK_CONFIG = {
    "platform": "template",
    "lock": {
        "service": "test.automation",
        "data_template": {
            "action": "lock",
            "caller": "{{ this.entity_id }}",
        },
    },
    "unlock": {
        "service": "test.automation",
        "data_template": {
            "action": "unlock",
            "caller": "{{ this.entity_id }}",
        },
    },
    "open": {
        "service": "test.automation",
        "data_template": {
            "action": "open",
            "caller": "{{ this.entity_id }}",
        },
    },
}

OPTIMISTIC_CODED_LOCK_CONFIG = {
    "platform": "template",
    "lock": {
        "service": "test.automation",
        "data_template": {
            "action": "lock",
            "caller": "{{ this.entity_id }}",
            "code": "{{ code }}",
        },
    },
    "unlock": {
        "service": "test.automation",
        "data_template": {
            "action": "unlock",
            "caller": "{{ this.entity_id }}",
            "code": "{{ code }}",
        },
    },
}


@pytest.mark.parametrize(("count", "domain"), [(1, lock.DOMAIN)])
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
@pytest.mark.usefixtures("start_ha")
async def test_template_state(hass: HomeAssistant) -> None:
    """Test template."""
    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("lock.test_template_lock")
    assert state.state == LockState.LOCKED

    hass.states.async_set("switch.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("lock.test_template_lock")
    assert state.state == LockState.UNLOCKED

    hass.states.async_set("switch.test_state", STATE_OPEN)
    await hass.async_block_till_done()

    state = hass.states.get("lock.test_template_lock")
    assert state.state == LockState.OPEN


@pytest.mark.parametrize(("count", "domain"), [(1, lock.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            lock.DOMAIN: {
                **OPTIMISTIC_LOCK_CONFIG,
                "name": "Test lock",
                "optimistic": True,
                "value_template": "{{ states.switch.test_state.state }}",
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_open_lock_optimistic(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test optimistic open."""
    await setup.async_setup_component(hass, "switch", {})
    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("lock.test_lock")
    assert state.state == LockState.LOCKED

    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_OPEN,
        {ATTR_ENTITY_ID: "lock.test_lock"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["action"] == "open"
    assert calls[0].data["caller"] == "lock.test_lock"

    state = hass.states.get("lock.test_lock")
    assert state.state == LockState.OPEN


@pytest.mark.parametrize(("count", "domain"), [(1, lock.DOMAIN)])
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
@pytest.mark.usefixtures("start_ha")
async def test_template_state_boolean_on(hass: HomeAssistant) -> None:
    """Test the setting of the state with boolean on."""
    state = hass.states.get("lock.template_lock")
    assert state.state == LockState.LOCKED


@pytest.mark.parametrize(("count", "domain"), [(1, lock.DOMAIN)])
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
@pytest.mark.usefixtures("start_ha")
async def test_template_state_boolean_off(hass: HomeAssistant) -> None:
    """Test the setting of the state with off."""
    state = hass.states.get("lock.template_lock")
    assert state.state == LockState.UNLOCKED


@pytest.mark.parametrize(("count", "domain"), [(0, lock.DOMAIN)])
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
        {
            lock.DOMAIN: {
                **OPTIMISTIC_LOCK_CONFIG,
                "value_template": "{{ 1 == 1 }}",
                "code_format_template": "{{ rubbish }",
            }
        },
        {
            lock.DOMAIN: {
                **OPTIMISTIC_LOCK_CONFIG,
                "value_template": "{{ 1 == 1 }}",
                "code_format_template": "{% if rubbish %}",
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_template_syntax_error(hass: HomeAssistant) -> None:
    """Test templating syntax errors don't create entities."""
    assert hass.states.async_all("lock") == []


@pytest.mark.parametrize(("count", "domain"), [(1, lock.DOMAIN)])
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
@pytest.mark.usefixtures("start_ha")
async def test_template_static(hass: HomeAssistant) -> None:
    """Test that we allow static templates."""
    state = hass.states.get("lock.template_lock")
    assert state.state == LockState.UNLOCKED

    hass.states.async_set("lock.template_lock", LockState.LOCKED)
    await hass.async_block_till_done()
    state = hass.states.get("lock.template_lock")
    assert state.state == LockState.LOCKED


@pytest.mark.parametrize(("count", "domain"), [(1, lock.DOMAIN)])
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
@pytest.mark.usefixtures("start_ha")
async def test_lock_action(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test lock action."""
    await setup.async_setup_component(hass, "switch", {})
    hass.states.async_set("switch.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == LockState.UNLOCKED

    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_LOCK,
        {ATTR_ENTITY_ID: "lock.template_lock"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["action"] == "lock"
    assert calls[0].data["caller"] == "lock.template_lock"


@pytest.mark.parametrize(("count", "domain"), [(1, lock.DOMAIN)])
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
@pytest.mark.usefixtures("start_ha")
async def test_unlock_action(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test unlock action."""
    await setup.async_setup_component(hass, "switch", {})
    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == LockState.LOCKED

    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: "lock.template_lock"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["action"] == "unlock"
    assert calls[0].data["caller"] == "lock.template_lock"


@pytest.mark.parametrize(("count", "domain"), [(1, lock.DOMAIN)])
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
@pytest.mark.usefixtures("start_ha")
async def test_open_action(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test open action."""
    await setup.async_setup_component(hass, "switch", {})
    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == LockState.LOCKED

    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_OPEN,
        {ATTR_ENTITY_ID: "lock.template_lock"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["action"] == "open"
    assert calls[0].data["caller"] == "lock.template_lock"


@pytest.mark.parametrize(("count", "domain"), [(1, lock.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            lock.DOMAIN: {
                **OPTIMISTIC_CODED_LOCK_CONFIG,
                "value_template": "{{ states.switch.test_state.state }}",
                "code_format_template": "{{ '.+' }}",
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_lock_action_with_code(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test lock action with defined code format and supplied lock code."""
    await setup.async_setup_component(hass, "switch", {})
    hass.states.async_set("switch.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == LockState.UNLOCKED

    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_LOCK,
        {ATTR_ENTITY_ID: "lock.template_lock", ATTR_CODE: "LOCK_CODE"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["action"] == "lock"
    assert calls[0].data["caller"] == "lock.template_lock"
    assert calls[0].data["code"] == "LOCK_CODE"


@pytest.mark.parametrize(("count", "domain"), [(1, lock.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            lock.DOMAIN: {
                **OPTIMISTIC_CODED_LOCK_CONFIG,
                "value_template": "{{ states.switch.test_state.state }}",
                "code_format_template": "{{ '.+' }}",
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_unlock_action_with_code(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test unlock action with code format and supplied unlock code."""
    await setup.async_setup_component(hass, "switch", {})
    hass.states.async_set("switch.test_state", STATE_ON)
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == LockState.LOCKED

    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: "lock.template_lock", ATTR_CODE: "UNLOCK_CODE"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["action"] == "unlock"
    assert calls[0].data["caller"] == "lock.template_lock"
    assert calls[0].data["code"] == "UNLOCK_CODE"


@pytest.mark.parametrize(("count", "domain"), [(1, lock.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            lock.DOMAIN: {
                **OPTIMISTIC_LOCK_CONFIG,
                "value_template": "{{ 1 == 1 }}",
                "code_format_template": "{{ '\\\\d+' }}",
            }
        },
    ],
)
@pytest.mark.parametrize(
    "test_action",
    [
        lock.SERVICE_LOCK,
        lock.SERVICE_UNLOCK,
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_lock_actions_fail_with_invalid_code(
    hass: HomeAssistant, calls: list[ServiceCall], test_action
) -> None:
    """Test invalid lock codes."""
    await hass.services.async_call(
        lock.DOMAIN,
        test_action,
        {ATTR_ENTITY_ID: "lock.template_lock", ATTR_CODE: "non-number-value"},
    )
    await hass.services.async_call(
        lock.DOMAIN,
        test_action,
        {ATTR_ENTITY_ID: "lock.template_lock"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 0


@pytest.mark.parametrize(("count", "domain"), [(1, lock.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            lock.DOMAIN: {
                **OPTIMISTIC_LOCK_CONFIG,
                "value_template": "{{ 1 == 1 }}",
                "code_format_template": "{{ 1/0 }}",
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_lock_actions_dont_execute_with_code_template_rendering_error(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test lock code format rendering fails block lock/unlock actions."""
    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_LOCK,
        {ATTR_ENTITY_ID: "lock.template_lock"},
    )
    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: "lock.template_lock", ATTR_CODE: "any-value"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 0


@pytest.mark.parametrize(("count", "domain"), [(1, lock.DOMAIN)])
@pytest.mark.parametrize("action", [lock.SERVICE_LOCK, lock.SERVICE_UNLOCK])
@pytest.mark.parametrize(
    "config",
    [
        {
            lock.DOMAIN: {
                **OPTIMISTIC_CODED_LOCK_CONFIG,
                "value_template": "{{ states.switch.test_state.state }}",
                "code_format_template": "{{ None }}",
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_actions_with_none_as_codeformat_ignores_code(
    hass: HomeAssistant, action, calls: list[ServiceCall]
) -> None:
    """Test lock actions with supplied lock code."""
    await setup.async_setup_component(hass, "switch", {})
    hass.states.async_set("switch.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == LockState.UNLOCKED

    await hass.services.async_call(
        lock.DOMAIN,
        action,
        {ATTR_ENTITY_ID: "lock.template_lock", ATTR_CODE: "any code"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["action"] == action
    assert calls[0].data["caller"] == "lock.template_lock"
    assert calls[0].data["code"] == "any code"


@pytest.mark.parametrize(("count", "domain"), [(1, lock.DOMAIN)])
@pytest.mark.parametrize("action", [lock.SERVICE_LOCK, lock.SERVICE_UNLOCK])
@pytest.mark.parametrize(
    "config",
    [
        {
            lock.DOMAIN: {
                **OPTIMISTIC_LOCK_CONFIG,
                "value_template": "{{ states.switch.test_state.state }}",
                "code_format_template": "[12]{1",
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_actions_with_invalid_regexp_as_codeformat_never_execute(
    hass: HomeAssistant, action, calls: list[ServiceCall]
) -> None:
    """Test lock actions don't execute with invalid regexp."""
    await setup.async_setup_component(hass, "switch", {})
    hass.states.async_set("switch.test_state", STATE_OFF)
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == LockState.UNLOCKED

    await hass.services.async_call(
        lock.DOMAIN,
        action,
        {ATTR_ENTITY_ID: "lock.template_lock", ATTR_CODE: "1"},
    )
    await hass.services.async_call(
        lock.DOMAIN,
        action,
        {ATTR_ENTITY_ID: "lock.template_lock", ATTR_CODE: "x"},
    )
    await hass.services.async_call(
        lock.DOMAIN,
        action,
        {ATTR_ENTITY_ID: "lock.template_lock"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 0


@pytest.mark.parametrize(("count", "domain"), [(1, lock.DOMAIN)])
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
    "test_state", [LockState.UNLOCKING, LockState.LOCKING, LockState.JAMMED]
)
@pytest.mark.usefixtures("start_ha")
async def test_lock_state(hass: HomeAssistant, test_state) -> None:
    """Test value template."""
    hass.states.async_set("input_select.test_state", test_state)
    await hass.async_block_till_done()

    state = hass.states.get("lock.template_lock")
    assert state.state == test_state


@pytest.mark.parametrize(("count", "domain"), [(1, lock.DOMAIN)])
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
@pytest.mark.usefixtures("start_ha")
async def test_available_template_with_entities(hass: HomeAssistant) -> None:
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


@pytest.mark.parametrize(("count", "domain"), [(1, lock.DOMAIN)])
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
@pytest.mark.usefixtures("start_ha")
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, caplog_setup_text
) -> None:
    """Test that an invalid availability keeps the device available."""
    assert hass.states.get("lock.template_lock").state != STATE_UNAVAILABLE
    assert ("UndefinedError: 'x' is undefined") in caplog_setup_text


@pytest.mark.parametrize(("count", "domain"), [(1, lock.DOMAIN)])
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
@pytest.mark.usefixtures("start_ha")
async def test_unique_id(hass: HomeAssistant) -> None:
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
