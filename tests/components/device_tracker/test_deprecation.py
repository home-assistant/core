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
    ("alias_name", "replacement", "replacement_name"),
    [
        (
            "BaseTrackerEntity",
            BaseTrackerEntity,
            "homeassistant.components.device_tracker.BaseTrackerEntity",
        ),
        (
            "ScannerEntity",
            ScannerEntity,
            "homeassistant.components.device_tracker.ScannerEntity",
        ),
        (
            "SourceType",
            SourceType,
            "homeassistant.components.device_tracker.SourceType",
        ),
        (
            "TrackerEntity",
            TrackerEntity,
            "homeassistant.components.device_tracker.TrackerEntity",
        ),
        (
            "TrackerEntityDescription",
            TrackerEntityDescription,
            "homeassistant.components.device_tracker.TrackerEntityDescription",
        ),
    ],
)
def test_deprecated_config_entry_aliases(
    caplog: pytest.LogCaptureFixture,
    alias_name: str,
    replacement: Any,
    replacement_name: str,
) -> None:
    """Test deprecated config_entry aliases."""
    import_and_test_deprecated_alias(
        caplog,
        config_entry,
        alias_name,
        replacement,
        "2027.6",
        replacement_name=replacement_name,
    )
