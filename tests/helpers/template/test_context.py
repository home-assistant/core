"""Test template context management for Home Assistant."""

import math
import traceback

import jinja2
import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import template
from homeassistant.helpers.template.context import (
    TemplateContextManager,
    render_with_context,
    template_context_manager,
    template_cv,
)


def test_template_context_manager() -> None:
    """Test TemplateContextManager functionality."""
    cm = TemplateContextManager()

    # Test setting template
    cm.set_template("{{ test }}", "rendering")
    assert template_cv.get() == ("{{ test }}", "rendering")

    # Test context manager exit
    cm.__exit__(None, None, None)
    assert template_cv.get() is None


def test_template_context_manager_context() -> None:
    """Test TemplateContextManager as context manager."""
    cm = TemplateContextManager()

    with cm:
        cm.set_template("{{ test }}", "parsing")
        assert template_cv.get() == ("{{ test }}", "parsing")

    # Should be cleared after exit
    assert template_cv.get() is None


def test_global_template_context_manager() -> None:
    """Test global template context manager instance."""
    # Should be an instance of TemplateContextManager
    assert isinstance(template_context_manager, TemplateContextManager)

    # Test it works like any other context manager
    template_context_manager.set_template("{{ global_test }}", "testing")
    assert template_cv.get() == ("{{ global_test }}", "testing")

    template_context_manager.__exit__(None, None, None)
    assert template_cv.get() is None


def test_render_with_context() -> None:
    """Test render_with_context function."""
    # Create a simple template
    env = jinja2.Environment()
    template_obj = env.from_string("Hello {{ name }}!")

    # Test rendering with context tracking
    result = render_with_context("Hello {{ name }}!", template_obj, name="World")
    assert result == "Hello World!"

    # Context should be cleared after rendering
    assert template_cv.get() is None


def test_render_with_context_sets_context() -> None:
    """Test that render_with_context properly sets template context."""
    context_during_render = []

    def capture_context() -> str:
        context_during_render.append(template_cv.get())
        return "rendered"

    env = jinja2.Environment()
    env.globals["capture_context"] = capture_context
    template_obj = env.from_string("{{ capture_context() }}")

    result = render_with_context("{{ test_template }}", template_obj)

    assert result == "rendered"
    # Should have captured the context during rendering
    assert context_during_render == [("{{ test_template }}", "rendering")]
    # Context should be cleared after rendering
    assert template_cv.get() is None


def test_render_with_context_bare_environment_globals() -> None:
    """Test rendering globals of a bare environment without variables."""
    env = jinja2.Environment()
    template_obj = env.from_string("{{ range(3) | list }} {{ name is defined }}")

    assert render_with_context("", template_obj) == "[0, 1, 2] False"


def test_render_variables_shadow_globals(hass: HomeAssistant) -> None:
    """Test render variables shadow globals without leaking into later renders."""
    shadowing = template.Template("{{ pi }} {{ extra | default('unset') }}", hass)
    other = template.Template("{{ pi }} {{ extra | default('unset') }}", hass)

    assert (
        shadowing.async_render({"pi": "shadowed", "extra": "set"}, parse_result=False)
        == "shadowed set"
    )
    assert shadowing.async_render(parse_result=False) == f"{math.pi} unset"
    assert other.async_render(parse_result=False) == f"{math.pi} unset"


def test_set_does_not_modify_globals(hass: HomeAssistant) -> None:
    """Test setting a name that is also a global keeps the global intact."""
    setting = template.Template("{% set pi = 'local' %}{{ pi }}", hass)
    reading = template.Template("{{ pi }}", hass)

    assert setting.async_render() == "local"
    assert reading.async_render() == math.pi
    assert setting.async_render() == "local"


@pytest.mark.parametrize(
    ("template_str", "expected"),
    [
        pytest.param(
            "{% import 'macros.jinja' as m %}{{ m.show() }}",
            ["unset 3.14", "unset 3.14"],
            id="import",
        ),
        pytest.param(
            "{% import 'macros.jinja' as m with context %}{{ m.show() }}",
            ["first 3.14", "second 3.14"],
            id="import_with_context",
        ),
        pytest.param(
            "{% from 'macros.jinja' import show %}{{ show() }}",
            ["unset 3.14", "unset 3.14"],
            id="from_import",
        ),
        pytest.param(
            "{% from 'macros.jinja' import show with context %}{{ show() }}",
            ["first 3.14", "second 3.14"],
            id="from_import_with_context",
        ),
        pytest.param(
            "{% include 'show.jinja' %}",
            ["first 3.14", "second 3.14"],
            id="include",
        ),
    ],
)
def test_custom_templates_see_variables_and_globals(
    hass: HomeAssistant, template_str: str, expected: list[str]
) -> None:
    """Test custom templates see globals, and render variables when given context."""
    template._get_hass_loader(hass).sources = {
        "macros.jinja": (
            "{% macro show() %}"
            "{{ my_var | default('unset') }} {{ pi | round(2) }}"
            "{% endmacro %}"
        ),
        "show.jinja": "{{ my_var | default('unset') }} {{ pi | round(2) }}",
    }
    tpl = template.Template(template_str, hass)

    assert [
        tpl.async_render({"my_var": "first"}, parse_result=False),
        tpl.async_render({"my_var": "second"}, parse_result=False),
    ] == expected


@pytest.mark.parametrize(
    ("template_str", "message", "line"),
    [
        pytest.param(
            "{{ 1 }}\n{{ 2 }}\n{{ 1 / 0 }}",
            "ZeroDivisionError: division by zero",
            3,
            id="python_error",
        ),
        pytest.param(
            "{{ states('sensor.missing') | float }}",
            "ValueError: Template error: float got invalid input 'unknown' when"
            " rendering template '{{ states('sensor.missing') | float }}' but no"
            " default was specified",
            1,
            id="template_error_with_source",
        ),
    ],
)
def test_render_error(
    hass: HomeAssistant, template_str: str, message: str, line: int
) -> None:
    """Test a render error raises TemplateError pointing at the template line."""
    with pytest.raises(TemplateError) as exc_info:
        template.Template(template_str, hass).async_render()

    assert str(exc_info.value) == message
    # Jinja rewrites the traceback so the template frame has the template line
    template_lines = [
        line_number
        for frame, line_number in traceback.walk_tb(
            exc_info.value.__cause__.__traceback__
        )
        if frame.f_code.co_filename == "<template>"
    ]
    assert template_lines == [line]
    assert template_cv.get() is None
