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
    ("exception_args", "exception_kwargs", "args_base_class", "message"),
    [
        ((), {}, (), ""),
        (("bla",), {}, ("bla",), "bla"),
        ((None,), {}, (None,), "None"),
        ((type_error_bla := TypeError("bla"),), {}, (type_error_bla,), "bla"),
        (
            (),
            {"translation_domain": "test", "translation_key": "test"},
            ("test",),
            "test",
        ),
        (
            (),
            {"translation_domain": "test", "translation_key": "bla"},
            ("bla",),
            "{bla} from cache",
        ),
        (
            (),
            {
                "translation_domain": "test",
                "translation_key": "bla",
                "translation_placeholders": {"bla": "Bla"},
            },
            ("bla",),
            "Bla from cache",
        ),
    ],
)
async def test_home_assistant_error(
    hass: HomeAssistant,
    exception_args: tuple[Any, ...],
    exception_kwargs: dict[str, Any],
    args_base_class: tuple[Any],
    message: str,
) -> None:
    """Test edge cases with HomeAssistantError."""

    with patch(
        "homeassistant.helpers.translation.async_get_cached_translations",
        return_value={"component.test.exceptions.bla.message": "{bla} from cache"},
    ):
        with pytest.raises(HomeAssistantError) as exc:
            raise HomeAssistantError(*exception_args, **exception_kwargs)
        assert exc.value.args == args_base_class
        assert str(exc.value) == message
        # Get string of exception again from the cache
        assert str(exc.value) == message


async def test_home_assistant_error_subclass(hass: HomeAssistant) -> None:
    """Test __str__ method on an HomeAssistantError subclass."""

    class _SubExceptionDefault(HomeAssistantError):
        """Sub class, default with generated message."""

    class _SubExceptionConstructor(HomeAssistantError):
        """Sub class with constructor, no generated message."""

        def __init__(
            self,
            custom_arg: str,
            translation_domain: str | None = None,
            translation_key: str | None = None,
            translation_placeholders: dict[str, str] | None = None,
        ) -> None:
            super().__init__(
                translation_domain=translation_domain,
                translation_key=translation_key,
                translation_placeholders=translation_placeholders,
            )
            self.custom_arg = custom_arg

    class _SubExceptionConstructorGenerate(HomeAssistantError):
        """Sub class with constructor, with generated message."""

        generate_message: bool = True

        def __init__(
            self,
            custom_arg: str,
            translation_domain: str | None = None,
            translation_key: str | None = None,
            translation_placeholders: dict[str, str] | None = None,
        ) -> None:
            super().__init__(
                translation_domain=translation_domain,
                translation_key=translation_key,
                translation_placeholders=translation_placeholders,
            )
            self.custom_arg = custom_arg

    class _SubExceptionGenerate(HomeAssistantError):
        """Sub class, no generated message."""

        generate_message: bool = True

    class _SubClassWithExceptionGroup(HomeAssistantError, BaseExceptionGroup):
        """Sub class with exception group, no generated message."""

    class _SubClassWithExceptionGroupGenerate(HomeAssistantError, BaseExceptionGroup):
        """Sub class with exception group and generated message."""

        generate_message: bool = True

    with patch(
        "homeassistant.helpers.translation.async_get_cached_translations",
        return_value={"component.test.exceptions.bla.message": "{bla} from cache"},
    ):
        # A subclass without a constructor generates a message by default
        with pytest.raises(HomeAssistantError) as exc:
            raise _SubExceptionDefault(
                translation_domain="test",
                translation_key="bla",
                translation_placeholders={"bla": "Bla"},
            )
        assert str(exc.value) == "Bla from cache"

        # A subclass with a constructor that does not parse `args` to the super class
        with pytest.raises(HomeAssistantError) as exc:
            raise _SubExceptionConstructor(
                "custom arg",
                translation_domain="test",
                translation_key="bla",
                translation_placeholders={"bla": "Bla"},
            )
        assert str(exc.value) == "Bla from cache"
        with pytest.raises(HomeAssistantError) as exc:
            raise _SubExceptionConstructor(
                "custom arg",
            )
        assert str(exc.value) == ""

        # A subclass with a constructor that generates the message
        with pytest.raises(HomeAssistantError) as exc:
            raise _SubExceptionConstructorGenerate(
                "custom arg",
                translation_domain="test",
                translation_key="bla",
                translation_placeholders={"bla": "Bla"},
            )
        assert str(exc.value) == "Bla from cache"

        # A subclass without overridden constructors and passed args
        # defaults to the passed args
        with pytest.raises(HomeAssistantError) as exc:
            raise _SubExceptionDefault(
                ValueError("wrong value"),
                translation_domain="test",
                translation_key="bla",
                translation_placeholders={"bla": "Bla"},
            )
        assert str(exc.value) == "wrong value"

        # A subclass without overridden constructors and passed args
        # and generate_message = True,  generates a message
        with pytest.raises(HomeAssistantError) as exc:
            raise _SubExceptionGenerate(
                ValueError("wrong value"),
                translation_domain="test",
                translation_key="bla",
                translation_placeholders={"bla": "Bla"},
            )
        assert str(exc.value) == "Bla from cache"

        # A subclass with an ExceptionGroup subclass requires a message to be passed.
        # As we pass args, we will not generate the message.
        # The __str__ constructor defaults to that of the super class.
        with pytest.raises(HomeAssistantError) as exc:
            raise _SubClassWithExceptionGroup(
                "group message",
                [ValueError("wrong value"), TypeError("wrong type")],
                translation_domain="test",
                translation_key="bla",
                translation_placeholders={"bla": "Bla"},
            )
        assert str(exc.value) == "group message (2 sub-exceptions)"
        with pytest.raises(HomeAssistantError) as exc:
            raise _SubClassWithExceptionGroup(
                "group message",
                [ValueError("wrong value"), TypeError("wrong type")],
            )
        assert str(exc.value) == "group message (2 sub-exceptions)"

        # A subclass with an ExceptionGroup subclass requires a message to be passed.
        # The `generate_message` flag is set.`
        # The __str__ constructor will return the generated message.
        with pytest.raises(HomeAssistantError) as exc:
            raise _SubClassWithExceptionGroupGenerate(
                "group message",
                [ValueError("wrong value"), TypeError("wrong type")],
                translation_domain="test",
                translation_key="bla",
                translation_placeholders={"bla": "Bla"},
            )
        assert str(exc.value) == "Bla from cache"
