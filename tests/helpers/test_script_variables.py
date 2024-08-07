"""Test script variables."""

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import TemplateError
from homeassistant.helpers import config_validation as cv


async def test_static_vars() -> None:
    """Test static vars."""
    orig = {"hello": "world"}
    var = cv.SCRIPT_VARIABLES_SCHEMA(orig)
    rendered = var.async_render(None, None)
    assert rendered is not orig
    assert rendered == orig


async def test_static_vars_run_args() -> None:
    """Test static vars."""
    orig = {"hello": "world"}
    orig_copy = dict(orig)
    var = cv.SCRIPT_VARIABLES_SCHEMA(orig)
    rendered = var.async_render(None, {"hello": "override", "run": "var"})
    assert rendered == {"hello": "override", "run": "var"}
    # Make sure we don't change original vars
    assert orig == orig_copy


async def test_static_vars_no_default() -> None:
    """Test static vars."""
    orig = {"hello": "world"}
    var = cv.SCRIPT_VARIABLES_SCHEMA(orig)
    rendered = var.async_render(None, None, render_as_defaults=False)
    assert rendered is not orig
    assert rendered == orig


async def test_static_vars_run_args_no_default() -> None:
    """Test static vars."""
    orig = {"hello": "world"}
    orig_copy = dict(orig)
    var = cv.SCRIPT_VARIABLES_SCHEMA(orig)
    rendered = var.async_render(
        None, {"hello": "override", "run": "var"}, render_as_defaults=False
    )
    assert rendered == {"hello": "world", "run": "var"}
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


async def test_template_vars_no_default(hass: HomeAssistant) -> None:
    """Test template vars."""
    var = cv.SCRIPT_VARIABLES_SCHEMA({"hello": "{{ 1 + 1 }}"})
    rendered = var.async_render(hass, None, render_as_defaults=False)
    assert rendered == {"hello": 2}


async def test_template_vars_run_args_no_default(hass: HomeAssistant) -> None:
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
        render_as_defaults=False,
    )
    assert rendered == {
        "run_var_ex": 5,
        "something": 6,
        "something_2": 6,
    }


async def test_template_vars_error(hass: HomeAssistant) -> None:
    """Test template vars."""
    var = cv.SCRIPT_VARIABLES_SCHEMA({"hello": "{{ canont.work }}"})
    with pytest.raises(TemplateError):
        var.async_render(hass, None)
