"""Test deprecation classes."""

from typing import Any

import pytest

from homeassistant.components.device_tracker import (
    BaseTrackerEntity,
    ScannerEntity,
    SourceType,
    TrackerEntity,
    TrackerEntityDescription,
    config_entry,
)

from tests.common import help_test_all, import_and_test_deprecated_alias


def test_all() -> None:
    """Test module.__all__ is correctly set."""
    help_test_all(config_entry)


@pytest.mark.parametrize(
    ("alias_name", "replacement"),
    [
        ("BaseTrackerEntity", BaseTrackerEntity),
        ("ScannerEntity", ScannerEntity),
        ("SourceType", SourceType),
        ("TrackerEntity", TrackerEntity),
        ("TrackerEntityDescription", TrackerEntityDescription),
    ],
)
def test_deprecated_aliases(
    caplog: pytest.LogCaptureFixture,
    alias_name: str,
    replacement: Any,
) -> None:
    """Test deprecated format constants."""
    import_and_test_deprecated_alias(
        caplog, config_entry, alias_name, replacement, "2027.6"
    )
