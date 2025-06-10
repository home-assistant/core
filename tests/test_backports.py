"""Test backports package."""

from __future__ import annotations

from enum import StrEnum
from types import ModuleType
from typing import Any

import pytest

from homeassistant.backports import enum as backports_enum

from .common import import_and_test_deprecated_alias


@pytest.mark.parametrize(
    ("module", "replacement", "breaks_in_ha_version"),
    [
        (backports_enum, StrEnum, "2025.5"),
    ],
)
def test_deprecated_aliases(
    caplog: pytest.LogCaptureFixture,
    module: ModuleType,
    replacement: Any,
    breaks_in_ha_version: str,
) -> None:
    """Test deprecated aliases."""
    alias_name = replacement.__name__
    import_and_test_deprecated_alias(
        caplog,
        module,
        alias_name,
        replacement,
        breaks_in_ha_version,
    )
