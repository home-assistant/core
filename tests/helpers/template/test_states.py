"""Test state wrapper classes and helpers for Home Assistant templates."""

from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext as does_not_raise
from datetime import timedelta

import pytest
from pytest_homeassistant.common import async_capture_events, async_fire_time_changed

from homeassistant.const import EVENT_STATE_CHANGED, STATE_ON
from homeassistant.core import Context, Event, HomeAssistant, callback
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.template import states as template_states
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from .helpers import render


async def test_template_states_blocks_setitem(hass: HomeAssistant) -> None:
    """Test we cannot setitem on TemplateStates."""
    hass.states.async_set("light.new", STATE_ON)
    state = hass.states.get("light.new")
    template_state = template.TemplateState(hass, state, True)
    with pytest.raises(RuntimeError):
        template_state["any"] = "any"


async def test_template_states_can_serialize(hass: HomeAssistant) -> None:
    """Test TemplateState is serializable."""
    hass.states.async_set("light.new", STATE_ON)
    state = hass.states.get("light.new")
    template_state = template.TemplateState(hass, state, True)
    assert template_state.as_dict() is template_state.as_dict()
    assert json_dumps(template_state) == json_dumps(template_state)


async def test_lru_increases_with_many_entities(hass: HomeAssistant) -> None:
    """Test that the template internal LRU cache increases with many entities."""
    # We do not actually want to record 4096 entities so we mock the entity count
    mock_entity_count = 16

    assert (
        template_states.CACHED_TEMPLATE_LRU.get_size()
        == template_states.CACHED_TEMPLATE_STATES
    )
    assert (
        template_states.CACHED_TEMPLATE_NO_COLLECT_LRU.get_size()
        == template_states.CACHED_TEMPLATE_STATES
    )
    template_states.CACHED_TEMPLATE_LRU.set_size(8)
    template_states.CACHED_TEMPLATE_NO_COLLECT_LRU.set_size(8)

    template.async_setup(hass)
    for i in range(mock_entity_count):
        hass.states.async_set(f"sensor.sensor{i}", "on")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=10))
    await hass.async_block_till_done()

    assert template_states.CACHED_TEMPLATE_LRU.get_size() == round(
        mock_entity_count * template_states.ENTITY_COUNT_GROWTH_FACTOR
    )
    assert template_states.CACHED_TEMPLATE_NO_COLLECT_LRU.get_size() == round(
        mock_entity_count * template_states.ENTITY_COUNT_GROWTH_FACTOR
    )

    await hass.async_stop()

    for i in range(mock_entity_count):
        hass.states.async_set(f"sensor.sensor_add_{i}", "on")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(minutes=20))
    await hass.async_block_till_done()

    assert template_states.CACHED_TEMPLATE_LRU.get_size() == round(
        mock_entity_count * template_states.ENTITY_COUNT_GROWTH_FACTOR
    )
    assert template_states.CACHED_TEMPLATE_NO_COLLECT_LRU.get_size() == round(
        mock_entity_count * template_states.ENTITY_COUNT_GROWTH_FACTOR
    )


def test_invalid_entity_id(hass: HomeAssistant) -> None:
    """Test referring states by entity id."""
    with pytest.raises(TemplateError):
        render(hass, '{{ states["big.fat..."] }}')
    with pytest.raises(TemplateError):
        render(hass, '{{ states.test["big.fat..."] }}')
    with pytest.raises(TemplateError):
        render(hass, '{{ states["invalid/domain"] }}')


def test_length_of_states(hass: HomeAssistant) -> None:
    """Test fetching the length of states."""
    hass.states.async_set("sensor.test", "23")
    hass.states.async_set("sensor.test2", "wow")
    hass.states.async_set("climate.test2", "cooling")

    result = render(hass, "{{ states | length }}")
    assert result == 3

    result = render(hass, "{{ states.sensor | length }}")
    assert result == 2


async def test_slice_states(hass: HomeAssistant) -> None:
    """Test iterating states with a slice."""
    hass.states.async_set("sensor.test", "23")

    result = render(
        hass,
        (
            "{% for states in states | slice(1) -%}{% set state = states | first %}"
            "{{ state.entity_id }}"
            "{%- endfor %}"
        ),
    )
    assert result == "sensor.test"


async def test_state_attributes(hass: HomeAssistant) -> None:
    """Test state attributes."""
    hass.states.async_set("sensor.test", "23")

    result = render(hass, "{{ states.sensor.test.last_changed }}")
    assert result == str(hass.states.get("sensor.test").last_changed)

    result = render(hass, "{{ states.sensor.test.object_id }}")
    assert result == hass.states.get("sensor.test").object_id

    result = render(hass, "{{ states.sensor.test.domain }}")
    assert result == hass.states.get("sensor.test").domain

    result = render(hass, "{{ states.sensor.test.context.id }}")
    assert result == hass.states.get("sensor.test").context.id

    result = render(hass, "{{ states.sensor.test.state_with_unit }}")
    assert result == 23

    result = render(hass, "{{ states.sensor.test.invalid_prop }}")
    assert result == ""

    with pytest.raises(TemplateError):
        render(hass, "{{ states.sensor.test.invalid_prop.xx }}")


async def test_unavailable_states(hass: HomeAssistant) -> None:
    """Test watching unavailable states."""

    for i in range(10):
        hass.states.async_set(f"light.sensor{i}", "on")

    hass.states.async_set("light.unavailable", "unavailable")
    hass.states.async_set("light.unknown", "unknown")
    hass.states.async_set("light.none", "none")

    result = render(
        hass,
        (
            "{{ states | selectattr('state', 'in', ['unavailable','unknown','none']) "
            "| sort(attribute='entity_id')"
            " | map(attribute='entity_id')"
            " | list | join(', ') }}"
        ),
    )
    assert result == "light.none, light.unavailable, light.unknown"

    result = render(
        hass,
        (
            "{{ states.light "
            "| selectattr('state', 'in', ['unavailable','unknown','none']) "
            "| sort(attribute='entity_id') | map(attribute='entity_id') | list "
            "| join(', ') }}"
        ),
    )
    assert result == "light.none, light.unavailable, light.unknown"


READABLE_PERSON = "person.readable"
UNREADABLE_PERSON = "person.secret"


def _entity_filter(entity_id: str) -> bool:
    return entity_id != UNREADABLE_PERSON


def _restricted(template_str: str, hass: HomeAssistant) -> template.Template:
    return template.Template(
        template_str, hass, entity_filter_factory=lambda: _entity_filter
    )


@pytest.fixture
def people(hass: HomeAssistant) -> None:
    """Set up a readable and an unreadable person and a group of both."""
    hass.states.async_set(
        READABLE_PERSON,
        "home",
        {"latitude": 32.87336, "longitude": -117.22743, "friendly_name": "Readable"},
    )
    hass.states.async_set(
        UNREADABLE_PERSON,
        "not_home",
        {"latitude": 52.52, "longitude": 13.405, "friendly_name": "Secret"},
    )
    hass.states.async_set(
        "group.people", "home", {"entity_id": [READABLE_PERSON, UNREADABLE_PERSON]}
    )


@pytest.mark.parametrize(
    ("template_str", "unfiltered", "filtered"),
    [
        pytest.param(
            "{{ states('person.secret') }}", "not_home", "unknown", id="states_call"
        ),
        pytest.param(
            "{{ states('Person.Secret') }}",
            "not_home",
            "unknown",
            id="states_call_mixed_case",
        ),
        pytest.param(
            "{{ 'person.secret' | states }}", "not_home", "unknown", id="states_filter"
        ),
        pytest.param(
            "{{ states.person.secret.state }}", "not_home", "", id="domain_attribute"
        ),
        pytest.param(
            "{{ states['person.secret'].state }}", "not_home", "", id="all_states_item"
        ),
        pytest.param(
            "{{ states.person | map(attribute='entity_id') | join(',') }}",
            "person.readable,person.secret",
            "person.readable",
            id="domain_iteration",
        ),
        pytest.param(
            "{{ states | map(attribute='entity_id') | sort | join(',') }}",
            "group.people,person.readable,person.secret",
            "group.people,person.readable",
            id="all_iteration",
        ),
        pytest.param("{{ states.person | count }}", "2", "1", id="domain_count"),
        pytest.param("{{ states | count }}", "3", "2", id="all_count"),
        pytest.param(
            "{{ state_attr('person.secret', 'latitude') }}",
            "52.52",
            "None",
            id="state_attr",
        ),
        pytest.param(
            "{{ state_attr('PERSON.SECRET', 'latitude') }}",
            "52.52",
            "None",
            id="state_attr_mixed_case",
        ),
        pytest.param(
            "{{ state_translated('person.secret') }}",
            "not_home",
            "unknown",
            id="state_translated",
        ),
        pytest.param(
            "{{ 'person.secret' | state_translated }}",
            "not_home",
            "unknown",
            id="state_translated_filter",
        ),
        pytest.param(
            "{{ 'person.secret' | state_attr_translated('latitude') }}",
            "52.52",
            "None",
            id="state_attr_translated_filter",
        ),
        pytest.param(
            "{{ is_state('person.secret', 'not_home') }}",
            "True",
            "False",
            id="is_state",
        ),
        pytest.param(
            "{{ has_value('person.secret') }}", "True", "False", id="has_value"
        ),
        pytest.param(
            "{{ expand('group.people') | map(attribute='entity_id') | sort | join(',') }}",
            "person.readable,person.secret",
            "person.readable",
            id="expand",
        ),
        pytest.param(
            "{{ distance('person.secret') is none }}", "False", "True", id="distance"
        ),
        pytest.param(
            "{{ closest(52.52, 13.405, states.person).entity_id }}",
            "person.secret",
            "person.readable",
            id="closest",
        ),
        pytest.param(
            "{{ entity_name('person.secret') }}", "Secret", "None", id="entity_name"
        ),
        pytest.param(
            "{{ entity_name('PERSON.SECRET') }}",
            "Secret",
            "None",
            id="entity_name_mixed_case",
        ),
    ],
)
@pytest.mark.usefixtures("people")
async def test_unreadable_entities_are_hidden(
    hass: HomeAssistant, template_str: str, unfiltered: str, filtered: str
) -> None:
    """Test the state of entities rejected by the entity filter cannot be read."""
    assert (
        template.Template(template_str, hass).async_render(parse_result=False)
        == unfiltered
    )
    assert _restricted(template_str, hass).async_render(parse_result=False) == (
        filtered
    )


@pytest.mark.usefixtures("people")
async def test_unreadable_entity_from_entity_id(hass: HomeAssistant) -> None:
    """Test a state looked up by entity ID is unknown if it cannot be read."""
    variables = {"this": template.TemplateStateFromEntityId(hass, UNREADABLE_PERSON)}

    assert _restricted("{{ this.state }}", hass).async_render(variables) == "unknown"


@pytest.mark.usefixtures("people")
async def test_unreadable_entity_from_mixed_case_entity_id(hass: HomeAssistant) -> None:
    """Test a state looked up by a mixed-case entity ID fails if it cannot be read."""
    variables = {"this": template.TemplateStateFromEntityId(hass, "Person.Secret")}

    assert template.Template("{{ this.state }}", hass).async_render(variables) == (
        "not_home"
    )
    with pytest.raises(TemplateError, match="Invalid entity id"):
        _restricted("{{ this.state }}", hass).async_render(variables)


@pytest.mark.parametrize(
    "template_str",
    [
        pytest.param("{{ states('person.secret') }}", id="states_call"),
        pytest.param("{{ states('Person.Secret') }}", id="states_call_mixed_case"),
        pytest.param("{{ states.person.secret }}", id="domain_attribute"),
        pytest.param("{{ states['person.secret'] }}", id="all_states_item"),
        pytest.param("{{ state_translated('person.secret') }}", id="state_translated"),
    ],
)
async def test_unreadable_entities_are_tracked_like_missing(
    hass: HomeAssistant, template_str: str
) -> None:
    """Test unreadable states are tracked like missing ones."""
    info = template.Template(template_str, hass).async_render_to_info()
    assert info.entities == {UNREADABLE_PERSON}

    hass.states.async_set(UNREADABLE_PERSON, "not_home")
    info = _restricted(template_str, hass).async_render_to_info()
    assert info.entities == {UNREADABLE_PERSON}


@pytest.mark.parametrize(
    "template_str",
    [
        pytest.param("{{ states['Person.Secret'].state }}", id="all_states_item"),
        pytest.param("{{ states.person.Secret.state }}", id="domain_attribute"),
        pytest.param("{{ state_translated('Person.Secret') }}", id="state_translated"),
    ],
)
@pytest.mark.usefixtures("people")
async def test_unreadable_entity_mixed_case_is_invalid(
    hass: HomeAssistant, template_str: str
) -> None:
    """Test a mixed-case ID of an unreadable entity is invalid like a missing one."""
    assert template.Template(template_str, hass).async_render() == "not_home"
    with pytest.raises(TemplateError, match="Invalid entity ID"):
        _restricted(template_str, hass).async_render()


@pytest.mark.usefixtures("people")
async def test_unreadable_entities_with_possible_json_value(
    hass: HomeAssistant,
) -> None:
    """Test rendering with a value hides entities the template cannot read."""
    tpl = _restricted("{{ value }} {{ states('person.secret') }}", hass)

    assert tpl.async_render_with_possible_json_value("value") == "value unknown"


@pytest.mark.parametrize(
    ("entity_filter_factory", "expectation"),
    [
        pytest.param(None, pytest.raises(TemplateError), id="readable"),
        pytest.param(lambda: _entity_filter, does_not_raise(), id="unreadable"),
    ],
)
@pytest.mark.usefixtures("people")
async def test_unreadable_entities_in_timeout_check(
    hass: HomeAssistant,
    entity_filter_factory: Callable[[], Callable[[str], bool]] | None,
    expectation: AbstractContextManager,
) -> None:
    """Test the timeout check renders in its thread with the same filter."""
    tpl = template.Template(
        "{% if is_state('person.secret', 'not_home') %}{{ 1 / 0 }}{% endif %}",
        hass,
        entity_filter_factory=entity_filter_factory,
    )

    with expectation:
        assert await tpl.async_render_will_timeout(3) is False


@pytest.mark.usefixtures("people")
async def test_entity_filter_is_resolved_per_render(hass: HomeAssistant) -> None:
    """Test the entity filter factory is called again for every render."""
    entity_filter: Callable[[str], bool] | None = _entity_filter
    tpl = template.Template(
        "{{ states('person.secret') }}",
        hass,
        entity_filter_factory=lambda: entity_filter,
    )
    assert tpl.async_render() == "unknown"

    entity_filter = None
    assert tpl.async_render() == "not_home"


@pytest.mark.parametrize(
    "template_str",
    [
        pytest.param(
            "{{ states('person.secret') }} {{ states('person.readable') }}",
            id="entity",
        ),
        pytest.param("{{ states.person | list }}", id="domain"),
        pytest.param("{{ states | list }}", id="all"),
    ],
)
@pytest.mark.usefixtures("people")
async def test_unreadable_entities_do_not_trigger_renders(
    hass: HomeAssistant, template_str: str
) -> None:
    """Test changes of unreadable entities do not trigger a new render."""
    info = _restricted(template_str, hass).async_render_to_info()

    assert info.filter(READABLE_PERSON)
    assert not info.filter(UNREADABLE_PERSON)
    assert not info.filter_lifecycle(UNREADABLE_PERSON)


@pytest.mark.parametrize(
    "sources",
    [
        pytest.param(
            {
                "tools.jinja": (
                    "{% set value = states('person.secret') %}"
                    "{% macro secret() %}{{ value }}{% endmacro %}"
                )
            },
            id="direct",
        ),
        pytest.param(
            {
                "tools.jinja": (
                    "{% from 'inner.jinja' import inner %}"
                    "{% macro secret() %}{{ inner() }}{% endmacro %}"
                ),
                "inner.jinja": (
                    "{% set value = states('person.secret') %}"
                    "{% macro inner() %}{{ value }}{% endmacro %}"
                ),
            },
            id="nested",
        ),
    ],
)
@pytest.mark.usefixtures("people")
async def test_unreadable_entities_in_imported_module(
    hass: HomeAssistant, sources: dict[str, str]
) -> None:
    """Test imported modules are not shared between filtered and other renders."""
    template._get_hass_loader(hass).sources = sources
    template_str = "{% from 'tools.jinja' import secret %}{{ secret() }}"

    assert _restricted(template_str, hass).async_render() == "unknown"
    assert template.Template(template_str, hass).async_render() == "not_home"
    assert _restricted(template_str, hass).async_render() == "unknown"


async def test_origin_event_cannot_be_read(hass: HomeAssistant) -> None:
    """Test the event that started a context is not available to filtered renders."""
    # State changed events are only created when something listens for them
    async_capture_events(hass, EVENT_STATE_CHANGED)
    context = Context()
    hass.states.async_set(UNREADABLE_PERSON, "not_home", context=context)
    hass.states.async_set("group.people", "not_home", context=context)
    template_str = "{{ states.group.people.context.origin_event.data.entity_id }}"

    assert template.Template(template_str, hass).async_render() == UNREADABLE_PERSON
    with pytest.raises(TemplateError, match="access to attribute 'origin_event'"):
        _restricted(template_str, hass).async_render()


async def test_entity_filter_factory_in_equality(hass: HomeAssistant) -> None:
    """Test templates with a different entity filter factory are not equal."""
    template_str = "{{ states('person.secret') }}"

    assert _restricted(template_str, hass) != template.Template(template_str, hass)


async def test_entity_filter_does_not_escape_into_scheduled_work(
    hass: HomeAssistant,
) -> None:
    """Test the entity filter does not apply to work scheduled during the render."""
    # system_log fires its event from a copy of the context of the logging code
    assert await async_setup_component(
        hass, "system_log", {"system_log": {"fire_event": True}}
    )
    hass.states.async_set(UNREADABLE_PERSON, "not_home")
    renders: list[str] = []

    @callback
    def _render_on_event(event: Event) -> None:
        renders.append(
            template.Template("{{ states('person.secret') }}", hass).async_render()
        )

    hass.bus.async_listen("system_log_event", _render_on_event)

    # Calling an undefined variable logs an error from inside the render
    with pytest.raises(TemplateError):
        _restricted("{{ nope.startswith('x') }}", hass).async_render()

    await hass.async_block_till_done()

    assert renders == ["not_home"]
