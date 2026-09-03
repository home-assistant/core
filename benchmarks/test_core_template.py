"""CodSpeed benchmarks for the template engine.

Templates render on dashboards, in automations and in many entity attributes.
Both the compile step and the warm render matter, and templates that walk the
state machine scale with the number of entities.

Run locally with: ``pytest benchmarks --codspeed``.
"""

from collections.abc import Callable

import pytest
from pytest_codspeed import BenchmarkFixture

from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

_STATES_TEMPLATE = (
    "{{ (states('sensor.power') | float / 1000) | round(2) }} kW "
    "{{ is_state('binary_sensor.motion', 'on') }} "
    "{{ state_attr('sensor.power', 'unit_of_measurement') }}"
)


def test_template_compile(benchmark: BenchmarkFixture, hass: HomeAssistant) -> None:
    """Compile a template from source (parse plus codegen).

    A unique source on every call (a varying Jinja comment) keeps the
    environment's template cache missing, so each run actually compiles instead
    of returning cached bytecode. The comment is stripped during compilation, so
    the cost matches the real template.
    """
    counter = 0

    def _compile() -> Template:
        nonlocal counter
        counter += 1
        template = Template(f"{{# {counter} #}}{_STATES_TEMPLATE}", hass)
        template.ensure_valid()
        return template

    template = benchmark(_compile)

    assert template.is_static is False


def test_template_render_simple(
    benchmark: BenchmarkFixture, hass: HomeAssistant
) -> None:
    """Render a pure-math template (warm), the engine's baseline overhead."""
    template = Template("{{ 1 + 1 }}", hass)
    template.ensure_valid()

    result = benchmark(template.async_render)

    assert result == 2


def test_template_render_states(
    benchmark: BenchmarkFixture, hass: HomeAssistant
) -> None:
    """Render a template that reads states, attributes and a filter (warm)."""
    hass.states.async_set("sensor.power", "1200", {"unit_of_measurement": "W"})
    hass.states.async_set("binary_sensor.motion", "on")
    template = Template(_STATES_TEMPLATE, hass)
    template.ensure_valid()

    result = benchmark(template.async_render)

    assert result.startswith("1.2 kW")


def test_template_render_to_info(
    benchmark: BenchmarkFixture, hass: HomeAssistant
) -> None:
    """Render and collect the entity dependency filter (the tracking path).

    ``async_render_to_info`` is what template triggers and template entities use
    to learn which entities to subscribe to.
    """
    hass.states.async_set("sensor.power", "1200", {"unit_of_measurement": "W"})
    hass.states.async_set("binary_sensor.motion", "on")
    template = Template(_STATES_TEMPLATE, hass)
    template.ensure_valid()

    info = benchmark(template.async_render_to_info)

    assert info.entities or info.all_states


@pytest.mark.parametrize("count", [10, 100, 1000])
def test_template_iterate_states(
    benchmark: BenchmarkFixture,
    populate_states: Callable[[int], None],
    hass: HomeAssistant,
    count: int,
) -> None:
    """Render a template that walks every sensor state, at several sizes.

    This is where an O(n) template touches an O(n) state machine; the cost
    should grow linearly and a worse-than-linear regression should stand out.
    """
    populate_states(count)
    template = Template(
        "{{ states.sensor | selectattr('state', 'eq', '1') | list | count }}",
        hass,
    )
    template.ensure_valid()

    result = benchmark(template.async_render)

    assert result == 1
