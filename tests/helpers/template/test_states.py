"""Test state wrapper classes and helpers for Home Assistant templates."""

from datetime import timedelta

import pytest

from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
from homeassistant.helpers.json import json_dumps
from homeassistant.helpers.template import states as template_states
from homeassistant.util import dt as dt_util

from .helpers import render

from tests.common import async_fire_time_changed


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
