"""The tests for the Template lock platform."""

from typing import Any

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant import setup
from homeassistant.components import lock, template
from homeassistant.components.lock import LockEntityFeature, LockState
from homeassistant.const import (
    ATTR_CODE,
    ATTR_ENTITY_ID,
    STATE_OFF,
    STATE_ON,
    STATE_OPEN,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.typing import ConfigType

from .conftest import (
    ConfigurationStyle,
    TemplatePlatformSetup,
    async_get_flow_preview_state,
    async_trigger,
    make_test_trigger,
    setup_and_test_nested_unique_id,
    setup_and_test_unique_id,
    setup_entity,
)

from tests.common import MockConfigEntry, assert_setup_component
from tests.typing import WebSocketGenerator

TEST_OBJECT_ID = "test_template_lock"
TEST_STATE_ENTITY_ID = "sensor.test_state"
TEST_AVAILABILITY_ENTITY_ID = "availability_state.state"
TEST_LOCK = TemplatePlatformSetup(
    lock.DOMAIN,
    None,
    "test_template_lock",
    make_test_trigger(
        TEST_AVAILABILITY_ENTITY_ID,
        TEST_STATE_ENTITY_ID,
    ),
)

LOCK_ACTION = {
    "lock": {
        "service": "test.automation",
        "data_template": {
            "action": "lock",
            "caller": "{{ this.entity_id }}",
            "code": "{{ code if code is defined else None }}",
        },
    },
}
UNLOCK_ACTION = {
    "unlock": {
        "service": "test.automation",
        "data_template": {
            "action": "unlock",
            "caller": "{{ this.entity_id }}",
            "code": "{{ code if code is defined else None }}",
        },
    },
}
OPEN_ACTION = {
    "open": {
        "service": "test.automation",
        "data_template": {
            "action": "open",
            "caller": "{{ this.entity_id }}",
        },
    },
}


OPTIMISTIC_LOCK = {
    **LOCK_ACTION,
    **UNLOCK_ACTION,
}


OPTIMISTIC_LOCK_CONFIG = {
    "platform": "template",
    **LOCK_ACTION,
    **UNLOCK_ACTION,
    **OPEN_ACTION,
}

OPTIMISTIC_CODED_LOCK_CONFIG = {
    "platform": "template",
    **LOCK_ACTION,
    **UNLOCK_ACTION,
}


@pytest.fixture
async def setup_lock(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    config: dict[str, Any],
) -> None:
    """Do setup of lock integration."""
    await setup_entity(hass, TEST_LOCK, style, count, config)


@pytest.fixture
async def setup_base_lock(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
    extra_config: dict,
):
    """Do setup of lock integration using a state template."""
    await setup_entity(hass, TEST_LOCK, style, count, extra_config, state_template)


@pytest.fixture
async def setup_state_lock(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
):
    """Do setup of lock integration using a state template."""
    await setup_entity(hass, TEST_LOCK, style, count, OPTIMISTIC_LOCK, state_template)


@pytest.fixture
async def setup_state_lock_with_extra_config(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
    extra_config: dict,
):
    """Do setup of cover integration using a state template."""
    await setup_entity(
        hass, TEST_LOCK, style, count, OPTIMISTIC_LOCK, state_template, extra_config
    )


@pytest.fixture
async def setup_state_lock_with_attribute(
    hass: HomeAssistant,
    count: int,
    style: ConfigurationStyle,
    state_template: str,
    attribute: str,
    attribute_template: str,
):
    """Do setup of cover integration using a state template."""
    await setup_entity(
        hass,
        TEST_LOCK,
        style,
        count,
        OPTIMISTIC_LOCK,
        state_template,
        {attribute: attribute_template} if attribute else {},
    )


@pytest.mark.parametrize(
    ("count", "state_template"), [(1, "{{ states.sensor.test_state.state }}")]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_lock")
async def test_template_state(hass: HomeAssistant) -> None:
    """Test template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == LockState.LOCKED

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == LockState.UNLOCKED

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OPEN)

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == LockState.OPEN


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ states.sensor.test_state.state }}", {"optimistic": True, **OPEN_ACTION})],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_lock_with_extra_config")
async def test_open_lock_optimistic(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test optimistic open."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == LockState.LOCKED

    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_OPEN,
        {ATTR_ENTITY_ID: TEST_LOCK.entity_id},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["action"] == "open"
    assert calls[0].data["caller"] == TEST_LOCK.entity_id

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == LockState.OPEN


@pytest.mark.parametrize(("count", "state_template"), [(1, "{{ 1 == 1 }}")])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_lock")
async def test_template_state_boolean_on(hass: HomeAssistant) -> None:
    """Test the setting of the state with boolean on."""
    # Ensure the trigger executes for trigger configurations
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == LockState.LOCKED


@pytest.mark.parametrize(("count", "state_template"), [(1, "{{ 1 == 2 }}")])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_lock")
async def test_template_state_boolean_off(hass: HomeAssistant) -> None:
    """Test the setting of the state with off."""
    # Ensure the trigger executes for trigger configurations
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == LockState.UNLOCKED


@pytest.mark.parametrize("count", [0])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("state_template", "extra_config"),
    [
        ("{% if rubbish %}", OPTIMISTIC_LOCK),
        ("{{ rubbish }", OPTIMISTIC_LOCK),
        ("Invalid", {}),
        (
            "{{ 1==1 }}",
            {
                "not_value_template": "{{ states.sensor.test_state.state }}",
                **OPTIMISTIC_LOCK,
            },
        ),
    ],
)
@pytest.mark.usefixtures("setup_base_lock")
async def test_template_syntax_error(hass: HomeAssistant) -> None:
    """Test templating syntax errors don't create entities."""
    assert hass.states.async_all("lock") == []


@pytest.mark.parametrize(("count", "state_template"), [(0, "{{ 1==1 }}")])
@pytest.mark.parametrize("attribute_template", ["{{ rubbish }", "{% if rubbish %}"])
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "code_format_template"),
        (ConfigurationStyle.MODERN, "code_format"),
        (ConfigurationStyle.TRIGGER, "code_format"),
    ],
)
@pytest.mark.usefixtures("setup_state_lock_with_attribute")
async def test_template_code_template_syntax_error(hass: HomeAssistant) -> None:
    """Test templating code_format syntax errors don't create entities."""
    assert hass.states.async_all("lock") == []


@pytest.mark.parametrize(("count", "state_template"), [(1, "{{ 1 + 1 }}")])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_lock")
async def test_template_static(hass: HomeAssistant) -> None:
    """Test that we allow static templates."""
    hass.states.async_set(TEST_LOCK.entity_id, LockState.LOCKED)
    await hass.async_block_till_done()
    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == LockState.LOCKED


@pytest.mark.parametrize("count", [1])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    ("state_template", "expected"),
    [
        ("{{ True }}", LockState.LOCKED),
        ("{{ False }}", LockState.UNLOCKED),
        ("{{ x - 12 }}", STATE_UNAVAILABLE),
        ("{{ None }}", STATE_UNKNOWN),
    ],
)
@pytest.mark.usefixtures("setup_state_lock")
async def test_state_template(hass: HomeAssistant, expected: str) -> None:
    """Test state and value_template template."""
    # Ensure the trigger executes for trigger configurations
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == expected


@pytest.mark.parametrize(
    ("count", "state_template", "attribute"), [(1, "{{ 1==1 }}", "picture")]
)
@pytest.mark.parametrize(
    "attribute_template",
    ["{% if states.sensor.test_state.state %}/local/switch.png{% endif %}"],
)
@pytest.mark.parametrize(
    ("style", "initial_state"),
    [
        (ConfigurationStyle.MODERN, ""),
        (ConfigurationStyle.TRIGGER, None),
    ],
)
@pytest.mark.usefixtures("setup_state_lock_with_attribute")
async def test_picture_template(hass: HomeAssistant, initial_state: str) -> None:
    """Test entity_picture template."""
    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.attributes.get("entity_picture") == initial_state

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.attributes["entity_picture"] == "/local/switch.png"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute"), [(1, "{{ 1==1 }}", "icon")]
)
@pytest.mark.parametrize(
    "attribute_template",
    ["{% if states.sensor.test_state.state %}mdi:eye{% endif %}"],
)
@pytest.mark.parametrize(
    ("style", "initial_state"),
    [
        (ConfigurationStyle.MODERN, ""),
        (ConfigurationStyle.TRIGGER, None),
    ],
)
@pytest.mark.usefixtures("setup_state_lock_with_attribute")
async def test_icon_template(hass: HomeAssistant, initial_state: str) -> None:
    """Test entity_picture template."""
    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.attributes.get("icon") == initial_state

    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.attributes["icon"] == "mdi:eye"


@pytest.mark.parametrize(
    ("count", "state_template"), [(1, "{{ states.sensor.test_state.state }}")]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_lock")
async def test_lock_action(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test lock action."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == LockState.UNLOCKED

    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_LOCK,
        {ATTR_ENTITY_ID: TEST_LOCK.entity_id},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["action"] == "lock"
    assert calls[0].data["caller"] == TEST_LOCK.entity_id


@pytest.mark.parametrize(
    ("count", "state_template"), [(1, "{{ states.sensor.test_state.state }}")]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_lock")
async def test_unlock_action(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test unlock action."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == LockState.LOCKED

    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: TEST_LOCK.entity_id},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["action"] == "unlock"
    assert calls[0].data["caller"] == TEST_LOCK.entity_id


@pytest.mark.parametrize(
    ("count", "state_template", "extra_config"),
    [(1, "{{ states.sensor.test_state.state }}", OPEN_ACTION)],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_state_lock_with_extra_config")
async def test_open_action(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test open action."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == LockState.LOCKED

    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_OPEN,
        {ATTR_ENTITY_ID: TEST_LOCK.entity_id},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["action"] == "open"
    assert calls[0].data["caller"] == TEST_LOCK.entity_id


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ states.sensor.test_state.state }}",
            "{{ '.+' }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "code_format_template"),
        (ConfigurationStyle.MODERN, "code_format"),
        (ConfigurationStyle.TRIGGER, "code_format"),
    ],
)
@pytest.mark.usefixtures("setup_state_lock_with_attribute")
async def test_lock_action_with_code(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test lock action with defined code format and supplied lock code."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == LockState.UNLOCKED

    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_LOCK,
        {ATTR_ENTITY_ID: TEST_LOCK.entity_id, ATTR_CODE: "LOCK_CODE"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["action"] == "lock"
    assert calls[0].data["caller"] == TEST_LOCK.entity_id
    assert calls[0].data["code"] == "LOCK_CODE"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ states.sensor.test_state.state }}",
            "{{ '.+' }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "code_format_template"),
        (ConfigurationStyle.MODERN, "code_format"),
        (ConfigurationStyle.TRIGGER, "code_format"),
    ],
)
@pytest.mark.usefixtures("setup_state_lock_with_attribute")
async def test_unlock_action_with_code(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test unlock action with code format and supplied unlock code."""
    await setup.async_setup_component(hass, "switch", {})
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == LockState.LOCKED

    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: TEST_LOCK.entity_id, ATTR_CODE: "UNLOCK_CODE"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["action"] == "unlock"
    assert calls[0].data["caller"] == TEST_LOCK.entity_id
    assert calls[0].data["code"] == "UNLOCK_CODE"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ 1 == 1 }}",
            "{{ '\\\\d+' }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "code_format_template"),
        (ConfigurationStyle.MODERN, "code_format"),
        (ConfigurationStyle.TRIGGER, "code_format"),
    ],
)
@pytest.mark.parametrize(
    "test_action",
    [
        lock.SERVICE_LOCK,
        lock.SERVICE_UNLOCK,
    ],
)
@pytest.mark.usefixtures("setup_state_lock_with_attribute")
async def test_lock_actions_fail_with_invalid_code(
    hass: HomeAssistant, calls: list[ServiceCall], test_action
) -> None:
    """Test invalid lock codes."""
    # Ensure trigger entities updated
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    await hass.services.async_call(
        lock.DOMAIN,
        test_action,
        {ATTR_ENTITY_ID: TEST_LOCK.entity_id, ATTR_CODE: "non-number-value"},
    )
    await hass.services.async_call(
        lock.DOMAIN,
        test_action,
        {ATTR_ENTITY_ID: TEST_LOCK.entity_id},
    )
    await hass.async_block_till_done()

    assert len(calls) == 0


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ 1 == 1 }}",
            "{{ 1/0 }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "code_format_template"),
        (ConfigurationStyle.MODERN, "code_format"),
        (ConfigurationStyle.TRIGGER, "code_format"),
    ],
)
@pytest.mark.usefixtures("setup_state_lock_with_attribute")
async def test_lock_actions_dont_execute_with_code_template_rendering_error(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test lock code format rendering fails block lock/unlock actions."""

    # Ensure trigger entities updated
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_LOCK,
        {ATTR_ENTITY_ID: TEST_LOCK.entity_id},
    )
    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: TEST_LOCK.entity_id, ATTR_CODE: "any-value"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 0


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ states.sensor.test_state.state }}",
            "{{ None }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "code_format_template"),
        (ConfigurationStyle.MODERN, "code_format"),
        (ConfigurationStyle.TRIGGER, "code_format"),
    ],
)
@pytest.mark.parametrize("action", [lock.SERVICE_LOCK, lock.SERVICE_UNLOCK])
@pytest.mark.usefixtures("setup_state_lock_with_attribute")
async def test_actions_with_none_as_codeformat_ignores_code(
    hass: HomeAssistant, action, calls: list[ServiceCall]
) -> None:
    """Test lock actions with supplied lock code."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == LockState.UNLOCKED

    await hass.services.async_call(
        lock.DOMAIN,
        action,
        {ATTR_ENTITY_ID: TEST_LOCK.entity_id, ATTR_CODE: "any code"},
    )
    await hass.async_block_till_done()

    assert len(calls) == 1
    assert calls[0].data["action"] == action
    assert calls[0].data["caller"] == TEST_LOCK.entity_id
    assert calls[0].data["code"] == "any code"


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ states.sensor.test_state.state }}",
            "[12]{1",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "code_format_template"),
        (ConfigurationStyle.MODERN, "code_format"),
        (ConfigurationStyle.TRIGGER, "code_format"),
    ],
)
@pytest.mark.parametrize("action", [lock.SERVICE_LOCK, lock.SERVICE_UNLOCK])
@pytest.mark.usefixtures("setup_state_lock_with_attribute")
async def test_actions_with_invalid_regexp_as_codeformat_never_execute(
    hass: HomeAssistant, action, calls: list[ServiceCall]
) -> None:
    """Test lock actions don't execute with invalid regexp."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_OFF)

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == LockState.UNLOCKED

    await hass.services.async_call(
        lock.DOMAIN,
        action,
        {ATTR_ENTITY_ID: TEST_LOCK.entity_id, ATTR_CODE: "1"},
    )
    await hass.services.async_call(
        lock.DOMAIN,
        action,
        {ATTR_ENTITY_ID: TEST_LOCK.entity_id, ATTR_CODE: "x"},
    )
    await hass.services.async_call(
        lock.DOMAIN,
        action,
        {ATTR_ENTITY_ID: TEST_LOCK.entity_id},
    )
    await hass.async_block_till_done()

    assert len(calls) == 0


@pytest.mark.parametrize(
    ("count", "state_template"), [(1, "{{ states.sensor.test_state.state }}")]
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.LEGACY, ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.parametrize(
    "test_state",
    [
        LockState.LOCKED,
        LockState.UNLOCKED,
        LockState.OPEN,
        LockState.UNLOCKING,
        LockState.LOCKING,
        LockState.JAMMED,
        LockState.OPENING,
    ],
)
@pytest.mark.usefixtures("setup_state_lock")
async def test_lock_state(hass: HomeAssistant, test_state) -> None:
    """Test value template."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, test_state)

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == test_state


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ states('sensor.test_state') }}",
            "{{ is_state('availability_state.state', 'on') }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "availability_template"),
        (ConfigurationStyle.MODERN, "availability"),
        (ConfigurationStyle.TRIGGER, "availability"),
    ],
)
@pytest.mark.usefixtures("setup_state_lock_with_attribute")
async def test_available_template_with_entities(hass: HomeAssistant) -> None:
    """Test availability templates with values from other entities."""
    # When template returns true..
    hass.states.async_set(TEST_AVAILABILITY_ENTITY_ID, STATE_ON)
    await hass.async_block_till_done()

    # Device State should not be unavailable
    assert hass.states.get(TEST_LOCK.entity_id).state != STATE_UNAVAILABLE

    # When Availability template returns false
    hass.states.async_set(TEST_AVAILABILITY_ENTITY_ID, STATE_OFF)
    await hass.async_block_till_done()

    # device state should be unavailable
    assert hass.states.get(TEST_LOCK.entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize(
    ("count", "state_template", "attribute_template"),
    [
        (
            1,
            "{{ 1 + 1 }}",
            "{{ x - 12 }}",
        )
    ],
)
@pytest.mark.parametrize(
    ("style", "attribute"),
    [
        (ConfigurationStyle.LEGACY, "availability_template"),
        (ConfigurationStyle.MODERN, "availability"),
        (ConfigurationStyle.TRIGGER, "availability"),
    ],
)
@pytest.mark.usefixtures("setup_state_lock_with_attribute")
async def test_invalid_availability_template_keeps_component_available(
    hass: HomeAssistant, caplog_setup_text, caplog: pytest.LogCaptureFixture
) -> None:
    """Test that an invalid availability keeps the device available."""
    await async_trigger(hass, TEST_STATE_ENTITY_ID, STATE_ON)

    assert hass.states.get(TEST_LOCK.entity_id).state != STATE_UNAVAILABLE
    err = "'x' is undefined"
    assert err in caplog_setup_text or err in caplog.text


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
async def test_legacy_unique_id(hass: HomeAssistant) -> None:
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


@pytest.mark.parametrize("config", [OPTIMISTIC_LOCK])
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
async def test_unique_id(
    hass: HomeAssistant, style: ConfigurationStyle, config: ConfigType
) -> None:
    """Test unique_id option only creates one vacuum per id."""
    await setup_and_test_unique_id(hass, TEST_LOCK, style, config, "{{ 'on' }}")


@pytest.mark.parametrize("config", [OPTIMISTIC_LOCK])
@pytest.mark.parametrize(
    "style", [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER]
)
async def test_nested_unique_id(
    hass: HomeAssistant,
    style: ConfigurationStyle,
    config: ConfigType,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a template unique_id propagates to vacuum unique_ids."""
    await setup_and_test_nested_unique_id(
        hass, TEST_LOCK, style, entity_registry, config, "{{ 'on' }}"
    )


async def test_emtpy_action_config(hass: HomeAssistant) -> None:
    """Test configuration with empty script."""
    with assert_setup_component(1, lock.DOMAIN):
        assert await setup.async_setup_component(
            hass,
            lock.DOMAIN,
            {
                lock.DOMAIN: {
                    "platform": "template",
                    "value_template": "{{ 0 == 1 }}",
                    "lock": [],
                    "unlock": [],
                    "open": [],
                    "name": "test_template_lock",
                    "optimistic": True,
                },
            },
        )

    await hass.async_block_till_done()
    await hass.async_start()
    await hass.async_block_till_done()

    state = hass.states.get("lock.test_template_lock")
    assert state.attributes["supported_features"] == LockEntityFeature.OPEN

    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: "lock.test_template_lock"},
    )
    await hass.async_block_till_done()

    state = hass.states.get("lock.test_template_lock")
    assert state.state == LockState.UNLOCKED

    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_LOCK,
        {ATTR_ENTITY_ID: "lock.test_template_lock"},
    )
    await hass.async_block_till_done()

    state = hass.states.get("lock.test_template_lock")
    assert state.state == LockState.LOCKED


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "lock": [],
                "unlock": [],
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_lock")
async def test_optimistic(hass: HomeAssistant) -> None:
    """Test configuration with optimistic state."""

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == STATE_UNKNOWN

    # Ensure Trigger template entities update.
    await async_trigger(hass, TEST_STATE_ENTITY_ID, "anything")

    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_LOCK,
        {ATTR_ENTITY_ID: TEST_LOCK.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == LockState.LOCKED

    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_UNLOCK,
        {ATTR_ENTITY_ID: TEST_LOCK.entity_id},
        blocking=True,
    )

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == LockState.UNLOCKED


@pytest.mark.parametrize(
    ("count", "config"),
    [
        (
            1,
            {
                "state": "{{ is_state('sensor.test_state', 'on') }}",
                "lock": [],
                "unlock": [],
                "optimistic": False,
            },
        )
    ],
)
@pytest.mark.parametrize(
    "style",
    [ConfigurationStyle.MODERN, ConfigurationStyle.TRIGGER],
)
@pytest.mark.usefixtures("setup_lock")
async def test_not_optimistic(hass: HomeAssistant) -> None:
    """Test optimistic yaml option set to false."""
    await hass.services.async_call(
        lock.DOMAIN,
        lock.SERVICE_LOCK,
        {ATTR_ENTITY_ID: TEST_LOCK.entity_id},
        blocking=True,
    )

    # Ensure Trigger template entities update.
    hass.states.async_set(TEST_AVAILABILITY_ENTITY_ID, "anything")
    await hass.async_block_till_done()

    state = hass.states.get(TEST_LOCK.entity_id)
    assert state.state == LockState.UNLOCKED


async def test_setup_config_entry(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Tests creating a lock from a config entry."""

    hass.states.async_set(
        "sensor.test_state",
        LockState.LOCKED,
        {},
    )

    template_config_entry = MockConfigEntry(
        data={},
        domain=template.DOMAIN,
        options={
            "name": "My template",
            "state": "{{ states('sensor.test_state') }}",
            "lock": [],
            "unlock": [],
            "template_type": lock.DOMAIN,
        },
        title="My template",
    )
    template_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(template_config_entry.entry_id)
    await hass.async_block_till_done()

    state = hass.states.get("lock.my_template")
    assert state is not None
    assert state == snapshot


async def test_flow_preview(
    hass: HomeAssistant,
    hass_ws_client: WebSocketGenerator,
) -> None:
    """Test the config flow preview."""

    state = await async_get_flow_preview_state(
        hass,
        hass_ws_client,
        lock.DOMAIN,
        {
            "name": "My template",
            "state": "{{ 'locked' }}",
            "lock": [],
            "unlock": [],
        },
    )

    assert state["state"] == LockState.LOCKED
