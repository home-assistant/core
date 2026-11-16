"""Test typing helpers."""

from typing import Any

import pytest
from pytest_homeassistant.common import help_test_all, import_and_test_deprecated_alias

from homeassistant.helpers import typing as ha_typing


def test_all() -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(ha_typing)


@pytest.mark.parametrize(
    ("alias_name", "replacement", "replacement_name"),
    [
        (
            "UNDEFINED",
            ha_typing.Undefined,
            "homeassistant.helpers.typing.Undefined",
        ),
        (
            "UndefinedType",
            ha_typing.Undefined,
            "homeassistant.helpers.typing.Undefined",
        ),
    ],
)
def test_deprecated_undefined_aliases(
    caplog: pytest.LogCaptureFixture,
    alias_name: str,
    replacement: Any,
    replacement_name: str,
) -> None:
    """Test deprecated Undefined aliases."""
    import_and_test_deprecated_alias(
        caplog,
        ha_typing,
        alias_name,
        replacement,
        "2027.12",
        replacement_name=replacement_name,
    )
