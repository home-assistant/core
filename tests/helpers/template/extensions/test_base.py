"""Test base template extension."""

from __future__ import annotations

import pytest

from homeassistant.exceptions import TemplateError
from homeassistant.helpers.template import TemplateEnvironment
from homeassistant.helpers.template.extensions.base import (
    BaseTemplateExtension,
    TemplateFunction,
)


def test_hass_property_raises_when_hass_is_none() -> None:
    """Test that accessing hass property raises RuntimeError when hass is None."""
    # Create an environment without hass
    env = TemplateEnvironment(None)

    # Create a simple extension
    extension = BaseTemplateExtension(env)

    # Accessing hass property should raise RuntimeError
    with pytest.raises(
        RuntimeError,
        match=(
            "Home Assistant instance is not available. "
            "This property should only be used in extensions with "
            "functions marked requires_hass=True."
        ),
    ):
        _ = extension.hass


def test_requires_hass_functions_not_registered_without_hass() -> None:
    """Test that functions requiring hass are not registered when hass is None."""
    # Create an environment without hass
    env = TemplateEnvironment(None)

    # Create a test function
    def test_func() -> str:
        return "test"

    # Create extension with a function that requires hass
    extension = BaseTemplateExtension(
        env,
        functions=[
            TemplateFunction(
                "test_func",
                test_func,
                as_global=True,
                requires_hass=True,
            ),
        ],
    )

    # Function should not be registered
    assert "test_func" not in env.globals
    assert extension is not None  # Extension is created but function not registered


def test_requires_hass_false_functions_registered_without_hass() -> None:
    """Test that functions not requiring hass are registered even when hass is None."""
    # Create an environment without hass
    env = TemplateEnvironment(None)

    # Create a test function
    def test_func() -> str:
        return "test"

    # Create extension with a function that does not require hass
    extension = BaseTemplateExtension(
        env,
        functions=[
            TemplateFunction(
                "test_func",
                test_func,
                as_global=True,
                requires_hass=False,  # Explicitly False (default)
            ),
        ],
    )

    # Function should be registered
    assert "test_func" in env.globals
    assert extension is not None


def test_limited_ok_functions_not_registered_in_limited_env() -> None:
    """Test that functions with limited_ok=False raise error in limited env."""
    # Create a limited environment without hass
    env = TemplateEnvironment(None, limited=True)

    # Create test functions
    def allowed_func() -> str:
        return "allowed"

    def restricted_func() -> str:
        return "restricted"

    # Create extension with both types of functions
    extension = BaseTemplateExtension(
        env,
        functions=[
            TemplateFunction(
                "allowed_func",
                allowed_func,
                as_global=True,
                limited_ok=True,  # Allowed in limited environments
            ),
            TemplateFunction(
                "restricted_func",
                restricted_func,
                as_global=True,
                limited_ok=False,  # Not allowed in limited environments
            ),
        ],
    )

    # The allowed function should be registered and work
    assert "allowed_func" in env.globals
    assert env.globals["allowed_func"]() == "allowed"

    # The restricted function should be registered but raise TemplateError
    assert "restricted_func" in env.globals
    with pytest.raises(
        TemplateError,
        match="Use of 'restricted_func' is not supported in limited templates",
    ):
        env.globals["restricted_func"]()

    assert extension is not None


def test_limited_ok_true_functions_registered_in_limited_env() -> None:
    """Test that functions with limited_ok=True are registered in limited env."""
    # Create a limited environment without hass
    env = TemplateEnvironment(None, limited=True)

    # Create a test function
    def test_func() -> str:
        return "test"

    # Create extension with a function allowed in limited environments
    extension = BaseTemplateExtension(
        env,
        functions=[
            TemplateFunction(
                "test_func",
                test_func,
                as_global=True,
                limited_ok=True,  # Default is True
            ),
        ],
    )

    # Function should be registered
    assert "test_func" in env.globals
    assert extension is not None


def test_function_registered_as_global() -> None:
    """Test that functions can be registered as globals."""
    env = TemplateEnvironment(None)

    def test_func() -> str:
        return "global"

    extension = BaseTemplateExtension(
        env,
        functions=[
            TemplateFunction(
                "test_func",
                test_func,
                as_global=True,
            ),
        ],
    )

    # Function should be registered as a global
    assert "test_func" in env.globals
    assert env.globals["test_func"] is test_func
    assert extension is not None


def test_function_registered_as_filter() -> None:
    """Test that functions can be registered as filters."""
    env = TemplateEnvironment(None)

    def test_filter(value: str) -> str:
        return f"filtered_{value}"

    extension = BaseTemplateExtension(
        env,
        functions=[
            TemplateFunction(
                "test_filter",
                test_filter,
                as_filter=True,
            ),
        ],
    )

    # Function should be registered as a filter
    assert "test_filter" in env.filters
    assert env.filters["test_filter"] is test_filter
    # Should not be in globals since as_global=False
    assert "test_filter" not in env.globals
    assert extension is not None


def test_function_registered_as_test() -> None:
    """Test that functions can be registered as tests."""
    env = TemplateEnvironment(None)

    def test_check(value: str) -> bool:
        return value == "test"

    extension = BaseTemplateExtension(
        env,
        functions=[
            TemplateFunction(
                "test_check",
                test_check,
                as_test=True,
            ),
        ],
    )

    # Function should be registered as a test
    assert "test_check" in env.tests
    assert env.tests["test_check"] is test_check
    # Should not be in globals or filters
    assert "test_check" not in env.globals
    assert "test_check" not in env.filters
    assert extension is not None


def test_function_registered_as_multiple_types() -> None:
    """Test that functions can be registered as multiple types simultaneously."""
    env = TemplateEnvironment(None)

    def multi_func(value: str = "default") -> str:
        return f"multi_{value}"

    extension = BaseTemplateExtension(
        env,
        functions=[
            TemplateFunction(
                "multi_func",
                multi_func,
                as_global=True,
                as_filter=True,
                as_test=True,
            ),
        ],
    )

    # Function should be registered in all three places
    assert "multi_func" in env.globals
    assert env.globals["multi_func"] is multi_func
    assert "multi_func" in env.filters
    assert env.filters["multi_func"] is multi_func
    assert "multi_func" in env.tests
    assert env.tests["multi_func"] is multi_func
    assert extension is not None


def test_multiple_functions_registered() -> None:
    """Test that multiple functions can be registered at once."""
    env = TemplateEnvironment(None)

    def func1() -> str:
        return "one"

    def func2() -> str:
        return "two"

    def func3() -> str:
        return "three"

    extension = BaseTemplateExtension(
        env,
        functions=[
            TemplateFunction("func1", func1, as_global=True),
            TemplateFunction("func2", func2, as_filter=True),
            TemplateFunction("func3", func3, as_test=True),
        ],
    )

    # All functions should be registered in their respective places
    assert "func1" in env.globals
    assert "func2" in env.filters
    assert "func3" in env.tests
    assert extension is not None
