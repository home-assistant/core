"""Test to verify that Home Assistant exceptions work."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import pytest

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConditionErrorContainer,
    ConditionErrorIndex,
    ConditionErrorMessage,
    ConfigValidationError,
    HomeAssistantError,
    TemplateError,
)


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
    ("exception_args", "exception_kwargs", "translation_key", "message"),
    [
        ((), {}, "", ""),
        (("bla",), {}, "bla", "bla"),
        ((None,), {}, "None", "None"),
        ((TypeError("bla"),), {}, "bla", "bla"),
        (
            (),
            {"translation_domain": "test", "translation_key": "test"},
            "test",
            "test",
        ),
        (
            (),
            {"translation_domain": "test", "translation_key": "bla"},
            "bla",
            "{bla} from cache",
        ),
        (
            (),
            {
                "translation_domain": "test",
                "translation_key": "bla",
                "translation_placeholders": {"bla": "Bla"},
            },
            "bla",
            "Bla from cache",
        ),
    ],
)
async def test_home_assistant_error(
    hass: HomeAssistant,
    exception_args: tuple[Any,],
    exception_kwargs: dict[str, Any],
    translation_key: str,
    message: str,
) -> None:
    """Test edge cases with HomeAssistantError."""

    with pytest.raises(HomeAssistantError, match=translation_key) as exc:
        raise HomeAssistantError(*exception_args, **exception_kwargs)
    with patch(
        "homeassistant.helpers.translation.async_get_cached_translations",
        return_value={"component.test.exceptions.bla.message": "{bla} from cache"},
    ):
        assert str(exc.value) == message


@pytest.mark.parametrize(
    ("exception_args", "exception_kwargs", "translation_key", "message"),
    [
        (("", [ValueError("invalid")]), {}, "", " (1 sub-exception)"),
        (("bla", [ValueError("invalid")]), {}, "bla", "bla (1 sub-exception)"),
        (
            ("milk overflow", [TypeError("bla")]),
            {},
            "milk",
            "milk overflow (1 sub-exception)",
        ),
        (
            ("beer", [ValueError("invalid")]),
            {"translation_domain": "test", "translation_key": "test"},
            "test",
            "test",
        ),
        (
            ("beer", [ValueError("invalid")]),
            {"translation_domain": "test", "translation_key": "bla"},
            "bla",
            "{bla} from cache",
        ),
        (
            ("beer", [ValueError("invalid")]),
            {
                "translation_domain": "test",
                "translation_key": "bla",
                "translation_placeholders": {"bla": "Bla"},
            },
            "bla",
            "Bla from cache",
        ),
    ],
)
async def test_configuration_validation_error(
    hass: HomeAssistant,
    exception_args: tuple[Any,],
    exception_kwargs: dict[str, Any],
    translation_key: str,
    message: str,
) -> None:
    """Test edge cases with ConfigValidationError."""

    with pytest.raises(ConfigValidationError, match=translation_key) as exc:
        raise ConfigValidationError(*exception_args, **exception_kwargs)
    with patch(
        "homeassistant.helpers.translation.async_get_cached_translations",
        return_value={"component.test.exceptions.bla.message": "{bla} from cache"},
    ):
        assert str(exc.value) == message
