"""The tests for the Template automation."""

from datetime import timedelta
from unittest import mock

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components import automation
from homeassistant.components.template import trigger as template_trigger
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ENTITY_MATCH_ALL,
    SERVICE_TURN_OFF,
    STATE_UNAVAILABLE,
)
from homeassistant.core import Context, HomeAssistant, ServiceCall, callback
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed, mock_component


@pytest.fixture(autouse=True)
def setup_comp(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Initialize components."""
    mock_component(hass, "group")
    hass.states.async_set("test.entity", "hello")


@pytest.mark.parametrize(("count", "domain"), [(1, automation.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": (
                        '{{ states.test.entity.state == "world" and true }}'
                    ),
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {"id": "{{ trigger.id}}"},
                },
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_if_fires_on_change_bool(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test for firing on boolean change."""
    assert len(calls) == 0

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 1

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )
    hass.states.async_set("test.entity", "planet")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["id"] == 0


@pytest.mark.parametrize(("count", "domain"), [(1, automation.DOMAIN)])
@pytest.mark.parametrize(
    ("config", "call_setup"),
    [
        (
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "template",
                        "value_template": (
                            '{{ states.test.entity.state == "world" and "true" }}'
                        ),
                    },
                    "action": {"service": "test.automation"},
                }
            },
            [(1, "world", False)],
        ),
        (
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "template",
                        "value_template": (
                            '{{ states.test.entity.state == "world" and "TrUE" }}'
                        ),
                    },
                    "action": {"service": "test.automation"},
                }
            },
            [(1, "world", False)],
        ),
        (
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "template",
                        "value_template": (
                            '{{ states.test.entity.state == "world" and false }}'
                        ),
                    },
                    "action": {"service": "test.automation"},
                }
            },
            [(0, "world", False)],
        ),
        (
            {
                automation.DOMAIN: {
                    "trigger": {"platform": "template", "value_template": "true"},
                    "action": {"service": "test.automation"},
                }
            },
            [(0, "world", False)],
        ),
        (
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "template",
                        "value_template": '{{ "Anything other than true is false." }}',
                    },
                    "action": {"service": "test.automation"},
                }
            },
            [(0, "world", False)],
        ),
        (
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "template",
                        "value_template": '{{ is_state("test.entity", "world") }}',
                    },
                    "action": {"service": "test.automation"},
                }
            },
            [(1, "world", False)],
        ),
        (
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "template",
                        "value_template": '{{ is_state("test.entity", "hello") }}',
                    },
                    "action": {"service": "test.automation"},
                }
            },
            [(0, "world", False)],
        ),
        (
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "template",
                        "value_template": "{{ states.test.entity.state == 'world' }}",
                    },
                    "action": {"service": "test.automation"},
                }
            },
            [(1, "world", False), (1, "world", False)],
        ),
        (
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "template",
                        "value_template": '{{ states.test.entity.state == "hello" }}',
                    },
                    "action": {"service": "test.automation"},
                },
            },
            [(0, "world", True)],
        ),
        (
            {
                automation.DOMAIN: {
                    "trigger_variables": {"entity": "test.entity"},
                    "trigger": {
                        "platform": "template",
                        "value_template": (
                            '{{ is_state(entity|default("test.entity2"), "hello") }}'
                        ),
                    },
                    "action": {"service": "test.automation"},
                },
            },
            [(0, "hello", True), (0, "goodbye", True), (1, "hello", True)],
        ),
        (
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "template",
                        "value_template": """{%- if is_state("test.entity", "world") -%}
                                            true
                                            {%- else -%}
                                            false
                                            {%- endif -%}""",
                    },
                    "action": {"service": "test.automation"},
                }
            },
            [(0, "worldz", False), (0, "hello", True)],
        ),
        (
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "template",
                        "value_template": '{{ not is_state("test.entity", "world") }}',
                    },
                    "action": {"service": "test.automation"},
                }
            },
            [
                (0, "world", False),
                (1, "home", False),
                (1, "work", False),
                (1, "not_home", False),
                (1, "world", False),
                (2, "home", False),
            ],
        ),
        (
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "template",
                        "value_template": "{{ xyz | round(0) }}",
                    },
                    "action": {"service": "test.automation"},
                }
            },
            [(0, "world", False)],
        ),
        (
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "template",
                        "value_template": "{{ is_state('test.entity', 'world') }}",
                        "for": {"seconds": 0},
                    },
                    "action": {"service": "test.automation"},
                }
            },
            [(1, "world", False)],
        ),
        (
            {
                automation.DOMAIN: {
                    "trigger": {"platform": "template", "value_template": "{{ true }}"},
                    "action": {"service": "test.automation"},
                }
            },
            [(0, "hello", False)],
        ),
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_general(
    hass: HomeAssistant, call_setup, calls: list[ServiceCall]
) -> None:
    """Test for firing on change."""
    assert len(calls) == 0

    for call_len, call_name, call_force in call_setup:
        hass.states.async_set("test.entity", call_name, force_update=call_force)
        await hass.async_block_till_done()
        assert len(calls) == call_len


@pytest.mark.parametrize(("count", "domain"), [(1, automation.DOMAIN)])
@pytest.mark.parametrize(
    ("config", "call_setup"),
    [
        (
            {
                automation.DOMAIN: {
                    "trigger": {
                        "platform": "template",
                        "value_template": (
                            "{{ 84 / states.test.number.state|int == 42 }}"
                        ),
                    },
                    "action": {"service": "test.automation"},
                }
            },
            [
                (0, "1"),
                (1, "2"),
                (1, "0"),
                (1, "2"),
            ],
        ),
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_if_not_fires_because_fail(
    hass: HomeAssistant, call_setup, calls: list[ServiceCall]
) -> None:
    """Test for not firing after TemplateError."""
    assert len(calls) == 0

    for call_len, call_number in call_setup:
        hass.states.async_set("test.number", call_number)
        await hass.async_block_till_done()
        assert len(calls) == call_len


@pytest.mark.parametrize(("count", "domain"), [(1, automation.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": '{{ is_state("test.entity", "world") }}',
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": (
                            "{{ trigger.platform }}"
                            " - {{ trigger.entity_id }}"
                            " - {{ trigger.from_state.state }}"
                            " - {{ trigger.to_state.state }}"
                            " - {{ trigger.for }}"
                        )
                    },
                },
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_if_fires_on_change_with_template_advanced(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test for firing on change with template advanced."""
    context = Context()
    await hass.async_block_till_done()

    hass.states.async_set("test.entity", "world", context=context)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].context.parent_id == context.id
    assert calls[0].data["some"] == "template - test.entity - hello - world - None"


@pytest.mark.parametrize(("count", "domain"), [(1, automation.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            automation.DOMAIN: {
                "trigger": {"platform": "event", "event_type": "test_event"},
                "condition": [
                    {
                        "condition": "template",
                        "value_template": '{{ is_state("test.entity", "world") }}',
                    }
                ],
                "action": {"service": "test.automation"},
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_if_action(hass: HomeAssistant, calls: list[ServiceCall]) -> None:
    """Test for firing if action."""
    # Condition is not true yet
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 0

    # Change condition to true, but it shouldn't be triggered yet
    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0

    # Condition is true and event is triggered
    hass.bus.async_fire("test_event")
    await hass.async_block_till_done()
    assert len(calls) == 1


@pytest.mark.parametrize(("count", "domain"), [(1, automation.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            automation.DOMAIN: {
                "trigger": {"platform": "template", "value_template": "{{ "},
                "action": {"service": "test.automation"},
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_if_fires_on_change_with_bad_template(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test for firing on change with bad template."""
    assert hass.states.get("automation.automation_0").state == STATE_UNAVAILABLE


@pytest.mark.parametrize(("count", "domain"), [(1, automation.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ states.test.entity.state == 'world' }}",
                },
                "action": [
                    {"event": "test_event"},
                    {"wait_template": "{{ is_state(trigger.entity_id, 'hello') }}"},
                    {
                        "service": "test.automation",
                        "data_template": {
                            "some": (
                                "{{ trigger.platform }}"
                                " - {{ trigger.entity_id }}"
                                " - {{ trigger.from_state.state }}"
                                " - {{ trigger.to_state.state }}"
                                " - {{ trigger.for }}"
                            )
                        },
                    },
                ],
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_wait_template_with_trigger(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test using wait template with 'trigger.entity_id'."""
    await hass.async_block_till_done()

    @callback
    def event_handler(event):
        hass.states.async_set("test.entity", "hello")

    hass.bus.async_listen_once("test_event", event_handler)

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].data["some"] == "template - test.entity - hello - world - None"


async def test_if_fires_on_change_with_for(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test for firing on change with for."""
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ is_state('test.entity', 'world') }}",
                    "for": {"seconds": 5},
                },
                "action": {"service": "test.automation"},
            }
        },
    )

    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1


@pytest.mark.parametrize(("count", "domain"), [(1, automation.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": '{{ is_state("test.entity", "world") }}',
                    "for": {"seconds": 5},
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": (
                            "{{ trigger.platform }}"
                            " - {{ trigger.entity_id }}"
                            " - {{ trigger.from_state.state }}"
                            " - {{ trigger.to_state.state }}"
                            " - {{ trigger.for }}"
                        )
                    },
                },
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_if_fires_on_change_with_for_advanced(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test for firing on change with for advanced."""
    context = Context()
    await hass.async_block_till_done()

    hass.states.async_set("test.entity", "world", context=context)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].context.parent_id == context.id
    assert calls[0].data["some"] == "template - test.entity - hello - world - 0:00:05"


@pytest.mark.parametrize(("count", "domain"), [(1, automation.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": '{{ is_state("test.entity", "world") }}',
                    "for": {"seconds": 0},
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": (
                            "{{ trigger.platform }}"
                            " - {{ trigger.entity_id }}"
                            " - {{ trigger.from_state.state }}"
                            " - {{ trigger.to_state.state }}"
                            " - {{ trigger.for }}"
                        )
                    },
                },
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_if_fires_on_change_with_for_0_advanced(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test for firing on change with for: 0 advanced."""
    context = Context()
    await hass.async_block_till_done()

    hass.states.async_set("test.entity", "world", context=context)
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].context.parent_id == context.id
    assert calls[0].data["some"] == "template - test.entity - hello - world - 0:00:00"


@pytest.mark.parametrize(("count", "domain"), [(1, automation.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ is_state('test.entity', 'world') }}",
                    "for": 5,
                },
                "action": {
                    "service": "test.automation",
                    "data_template": {
                        "some": (
                            "{{ trigger.platform }}"
                            " - {{ trigger.entity_id }}"
                            " - {{ trigger.from_state.state }}"
                            " - {{ trigger.to_state.state }}"
                            " - {{ trigger.for }}"
                        )
                    },
                },
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_if_fires_on_change_with_for_2(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test for firing on change with for."""
    context = Context()
    hass.states.async_set("test.entity", "world", context=context)
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1
    assert calls[0].context.parent_id == context.id
    assert calls[0].data["some"] == "template - test.entity - hello - world - 0:00:05"


@pytest.mark.parametrize(("count", "domain"), [(1, automation.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ is_state('test.entity', 'world') }}",
                    "for": {"seconds": 5},
                },
                "action": {"service": "test.automation"},
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_if_not_fires_on_change_with_for(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test for firing on change with for."""
    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=4))
    await hass.async_block_till_done()
    assert len(calls) == 0
    hass.states.async_set("test.entity", "hello")
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()
    assert len(calls) == 0


@pytest.mark.parametrize(("count", "domain"), [(1, automation.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ is_state('test.entity', 'world') }}",
                    "for": {"seconds": 5},
                },
                "action": {"service": "test.automation"},
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_if_not_fires_when_turned_off_with_for(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test for firing on change with for."""
    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=4))
    await hass.async_block_till_done()
    assert len(calls) == 0
    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_MATCH_ALL},
        blocking=True,
    )
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=6))
    await hass.async_block_till_done()
    assert len(calls) == 0


@pytest.mark.parametrize(("count", "domain"), [(1, automation.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ is_state('test.entity', 'world') }}",
                    "for": {"seconds": "{{ 5 }}"},
                },
                "action": {"service": "test.automation"},
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_if_fires_on_change_with_for_template_1(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test for firing on change with for template."""
    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1


@pytest.mark.parametrize(("count", "domain"), [(1, automation.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ is_state('test.entity', 'world') }}",
                    "for": "{{ 5 }}",
                },
                "action": {"service": "test.automation"},
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_if_fires_on_change_with_for_template_2(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test for firing on change with for template."""
    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1


@pytest.mark.parametrize(("count", "domain"), [(1, automation.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ is_state('test.entity', 'world') }}",
                    "for": "00:00:{{ 5 }}",
                },
                "action": {"service": "test.automation"},
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_if_fires_on_change_with_for_template_3(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test for firing on change with for template."""
    hass.states.async_set("test.entity", "world")
    await hass.async_block_till_done()
    assert len(calls) == 0
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=10))
    await hass.async_block_till_done()
    assert len(calls) == 1


@pytest.mark.parametrize(("count", "domain"), [(1, automation.DOMAIN)])
@pytest.mark.parametrize(
    "config",
    [
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ is_state('test.entity', 'world') }}",
                    "for": {"seconds": "{{ five }}"},
                },
                "action": {"service": "test.automation"},
            }
        },
    ],
)
@pytest.mark.usefixtures("start_ha")
async def test_invalid_for_template_1(
    hass: HomeAssistant, calls: list[ServiceCall]
) -> None:
    """Test for invalid for template."""
    with mock.patch.object(template_trigger, "_LOGGER") as mock_logger:
        hass.states.async_set("test.entity", "world")
        await hass.async_block_till_done()
        assert mock_logger.error.called


async def test_if_fires_on_time_change(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, calls: list[ServiceCall]
) -> None:
    """Test for firing on time changes."""
    start_time = dt_util.utcnow() + timedelta(hours=24)
    time_that_will_not_match_right_away = start_time.replace(minute=1, second=0)
    freezer.move_to(time_that_will_not_match_right_away)
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: {
                "trigger": {
                    "platform": "template",
                    "value_template": "{{ utcnow().minute % 2 == 0 }}",
                },
                "action": {"service": "test.automation"},
            }
        },
    )
    await hass.async_block_till_done()
    assert len(calls) == 0

    # Trigger once (match template)
    first_time = start_time.replace(minute=2, second=0)
    freezer.move_to(first_time)
    async_fire_time_changed(hass, first_time)
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Trigger again (match template)
    second_time = start_time.replace(minute=4, second=0)
    freezer.move_to(second_time)
    async_fire_time_changed(hass, second_time)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Trigger again (do not match template)
    third_time = start_time.replace(minute=5, second=0)
    freezer.move_to(third_time)
    async_fire_time_changed(hass, third_time)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert len(calls) == 1

    # Trigger again (match template)
    forth_time = start_time.replace(minute=8, second=0)
    freezer.move_to(forth_time)
    async_fire_time_changed(hass, forth_time)
    await hass.async_block_till_done()
    await hass.async_block_till_done()
    assert len(calls) == 2
