"""Test to verify that Home Assistant exceptions work."""

from __future__ import annotations

from typing import Any

import pytest

from homeassistant.core import HomeAssistant, async_get_hass
from homeassistant.exceptions import (
    ConditionErrorContainer,
    ConditionErrorIndex,
    ConditionErrorMessage,
    HomeAssistantError,
    TemplateError,
)

from .common import async_mock_service


def test_conditionerror_format() -> None:
    """Test ConditionError stringifiers."""
    error1 = ConditionErrorMessage("test", "A test error")
    assert str(error1) == "In 'test' condition: A test error"

    error2 = ConditionErrorMessage("test", "Another error")
    assert str(error2) == "In 'test' condition: Another error"

    error_pos1 = ConditionErrorIndex("box", index=0, total=2, error=error1)
    assert (
        str(error_pos1)
        == """In 'box' (item 1 of 2):
  In 'test' condition: A test error"""
    )

    error_pos2 = ConditionErrorIndex("box", index=1, total=2, error=error2)
    assert (
        str(error_pos2)
        == """In 'box' (item 2 of 2):
  In 'test' condition: Another error"""
    )

    error_container1 = ConditionErrorContainer("box", errors=[error_pos1, error_pos2])
    assert (
        str(error_container1)
        == """In 'box' (item 1 of 2):
  In 'test' condition: A test error
In 'box' (item 2 of 2):
  In 'test' condition: Another error"""
    )

    error_pos3 = ConditionErrorIndex("box", index=0, total=1, error=error1)
    assert (
        str(error_pos3)
        == """In 'box':
  In 'test' condition: A test error"""
    )


@pytest.mark.parametrize(
    ("arg", "expected"),
    [
        ("message", "message"),
        (Exception("message"), "Exception: message"),
    ],
)
def test_template_message(arg: str | Exception, expected: str) -> None:
    """Ensure we can create TemplateError."""
    template_error = TemplateError(arg)
    assert str(template_error) == expected


@pytest.mark.parametrize(
    ("exception_args", "exception_kwargs", "message"),
    [
        ((), {}, ""),
        (("bla",), {}, "bla"),
        ((None,), {}, "None"),
        ((TypeError("bla"),), {}, "bla"),
        (
            (),
            {"translation_domain": "test", "translation_key": "bla"},
            "component.test.exceptions.bla.message",
        ),
    ],
)
async def test_home_assistant_error(
    hass: HomeAssistant,
    exception_args: tuple[Any,],
    exception_kwargs: dict[str, Any],
    message: str,
) -> None:
    """Test edge cases with HomeAssistantError."""

    assert async_get_hass() is hass
    async_mock_service(
        hass,
        "test_domain",
        "test_service",
        raise_exception=HomeAssistantError(*exception_args, **exception_kwargs),
    )
    with pytest.raises(HomeAssistantError, match=message) as exc:
        await hass.services.async_call(
            "test_domain",
            "test_service",
            service_data={},
            blocking=True,
        )
    assert str(exc.value) == message
