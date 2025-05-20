"""Test script variables."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.script_variables import ScriptRunVariables, ScriptVariables


async def test_static_vars() -> None:
    """Test static vars."""
    orig = {"hello": "world"}
    var = ScriptVariables(orig)
    rendered = var.async_render(None, None)
    assert rendered is not orig
    assert rendered == orig


async def test_static_vars_run_args() -> None:
    """Test static vars."""
    orig = {"hello": "world"}
    orig_copy = dict(orig)
    var = ScriptVariables(orig)
    rendered = var.async_render(None, {"hello": "override", "run": "var"})
    assert rendered == {"hello": "override", "run": "var"}
    # Make sure we don't change original vars
    assert orig == orig_copy


async def test_static_vars_simple() -> None:
    """Test static vars."""
    orig = {"hello": "world"}
    var = ScriptVariables(orig)
    rendered = var.async_simple_render({})
    assert rendered is orig


async def test_static_vars_run_args_simple() -> None:
    """Test static vars."""
    orig = {"hello": "world"}
    orig_copy = dict(orig)
    var = ScriptVariables(orig)
    rendered = var.async_simple_render({"hello": "override", "run": "var"})
    assert rendered is orig
    # Make sure we don't change original vars
    assert orig == orig_copy


async def test_template_vars(hass: HomeAssistant) -> None:
    """Test template vars."""
    var = cv.SCRIPT_VARIABLES_SCHEMA({"hello": "{{ 1 + 1 }}"})
    rendered = var.async_render(hass, None)
    assert rendered == {"hello": 2}


async def test_template_vars_run_args(hass: HomeAssistant) -> None:
    """Test template vars."""
    var = cv.SCRIPT_VARIABLES_SCHEMA(
        {
            "something": "{{ run_var_ex + 1 }}",
            "something_2": "{{ run_var_ex + 1 }}",
        }
    )
    rendered = var.async_render(
        hass,
        {
            "run_var_ex": 5,
            "something_2": 1,
        },
    )
    assert rendered == {
        "run_var_ex": 5,
        "something": 6,
        "something_2": 1,
    }


async def test_template_vars_simple(hass: HomeAssistant) -> None:
    """Test template vars."""
    var = cv.SCRIPT_VARIABLES_SCHEMA({"hello": "{{ 1 + 1 }}"})
    rendered = var.async_simple_render({})
    assert rendered == {"hello": 2}


async def test_template_vars_run_args_simple(hass: HomeAssistant) -> None:
    """Test template vars."""
    var = cv.SCRIPT_VARIABLES_SCHEMA(
        {
            "something": "{{ run_var_ex + 1 }}",
            "something_2": "{{ run_var_ex + 1 }}",
        }
    )
    rendered = var.async_simple_render(
        {
            "run_var_ex": 5,
            "something_2": 1,
        }
    )
    assert rendered == {
        "something": 6,
        "something_2": 6,
    }


async def test_template_vars_error(hass: HomeAssistant) -> None:
    """Test template vars."""
    var = cv.SCRIPT_VARIABLES_SCHEMA({"hello": "{{ canont.work }}"})
    with pytest.raises(TemplateError):
        var.async_render(hass, None)


async def test_script_vars_exit_top_level() -> None:
    """Test exiting top level script run variables."""
    script_vars = ScriptRunVariables.create_top_level()
    with pytest.raises(ValueError):
        script_vars.exit_scope()


async def test_script_vars_delete_var() -> None:
    """Test deleting from script run variables."""
    script_vars = ScriptRunVariables.create_top_level({"x": 1, "y": 2})
    with pytest.raises(TypeError):
        del script_vars["x"]
    with pytest.raises(TypeError):
        script_vars.pop("y")
    assert script_vars._full_scope == {"x": 1, "y": 2}


async def test_script_vars_scopes() -> None:
    """Test script run variables scopes."""
    script_vars = ScriptRunVariables.create_top_level()
    script_vars["x"] = 1
    script_vars["y"] = 1
    assert script_vars["x"] == 1
    assert script_vars["y"] == 1

    script_vars_2 = script_vars.enter_scope()
    script_vars_2.define_local("x", 2)
    assert script_vars_2["x"] == 2
    assert script_vars_2["y"] == 1

    script_vars_3 = script_vars_2.enter_scope()
    script_vars_3["x"] = 3
    script_vars_3["y"] = 3
    assert script_vars_3["x"] == 3
    assert script_vars_3["y"] == 3

    script_vars_4 = script_vars_3.enter_scope()
    assert script_vars_4["x"] == 3
    assert script_vars_4["y"] == 3

    assert script_vars_4.exit_scope() is script_vars_3

    assert script_vars_3._full_scope == {"x": 3, "y": 3}
    assert script_vars_3.local_scope == {}

    assert script_vars_3.exit_scope() is script_vars_2

    assert script_vars_2._full_scope == {"x": 3, "y": 3}
    assert script_vars_2.local_scope == {"x": 3}

    assert script_vars_2.exit_scope() is script_vars

    assert script_vars._full_scope == {"x": 1, "y": 3}
    assert script_vars.local_scope == {"x": 1, "y": 3}


async def test_script_vars_parallel() -> None:
    """Test script run variables parallel support."""
    script_vars = ScriptRunVariables.create_top_level({"x": 1, "y": 1, "z": 1})

    script_vars_2a = script_vars.enter_scope(parallel=True)
    script_vars_3a = script_vars_2a.enter_scope()

    script_vars_2b = script_vars.enter_scope(parallel=True)
    script_vars_3b = script_vars_2b.enter_scope()

    script_vars_3a["x"] = "a"
    script_vars_3a.assign_parallel_protected("y", "a")

    script_vars_3b["x"] = "b"
    script_vars_3b.assign_parallel_protected("y", "b")

    assert script_vars_3a._full_scope == {"x": "b", "y": "a", "z": 1}
    assert script_vars_3a.non_parallel_scope == {"x": "a", "y": "a"}

    assert script_vars_3b._full_scope == {"x": "b", "y": "b", "z": 1}
    assert script_vars_3b.non_parallel_scope == {"x": "b", "y": "b"}

    assert script_vars_3a.exit_scope() is script_vars_2a
    assert script_vars_2a.exit_scope() is script_vars
    assert script_vars_3b.exit_scope() is script_vars_2b
    assert script_vars_2b.exit_scope() is script_vars

    assert script_vars._full_scope == {"x": "b", "y": 1, "z": 1}
    assert script_vars.local_scope == {"x": "b", "y": 1, "z": 1}
