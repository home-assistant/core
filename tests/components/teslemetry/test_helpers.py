"""Test the Teslemetry helpers."""

import pytest

from homeassistant.components.teslemetry.helpers import firmware_at_least


@pytest.mark.parametrize(
    ("firmware", "minimum", "expected"),
    [
        ("2024.8", "2024.8", True),
        ("2024.8", "2024.44.25", False),
        ("2024.44.25", "2024.8", True),
        ("2024.44.25", "2024.44.25", True),
        ("2025.14", "2025.2.6", True),
        ("2025.2.6", "2025.14", False),
        ("Unknown", "2024.8", False),
        ("Unknown", "2025.14", False),
    ],
)
def test_firmware_at_least(firmware: str, minimum: str, expected: bool) -> None:
    """Test firmware_at_least correctly compares week-based firmware versions."""
    assert firmware_at_least(firmware, minimum) is expected
