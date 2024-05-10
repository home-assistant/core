"""Test backports package."""

from __future__ import annotations

from enum import StrEnum
from functools import cached_property
from types import ModuleType
from typing import Any

import pytest

from homeassistant.backports import (
    enum as backports_enum,
    functools as backports_functools,
)

from tests.common import import_and_test_deprecated_alias


@pytest.mark.parametrize(
    ("module", "replacement", "breaks_in_ha_version"),
    [
        (backports_enum, StrEnum, "2025.5"),
        (backports_functools, cached_property, "2025.5"),
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
