"""Tests for the Mawaqit types."""

import pytest

from homeassistant.components.mawaqit.types import MawaqitMosqueData


@pytest.mark.parametrize(
    ("proximity", "localisation", "expected"),
    [
        (1744, "Paris", "Mosque (1.74 km)"),
        (None, "Paris", "Mosque - Paris"),
        (None, None, "Mosque"),
    ],
    ids=["with_proximity", "with_localisation", "label_only"],
)
def test_display_name(
    proximity: int | None,
    localisation: str | None,
    expected: str,
) -> None:
    """Test display_name resolves through each branch."""
    mosque = MawaqitMosqueData(
        uuid="uuid",
        label="Mosque",
        name="Mosque",
        latitude=48.0,
        longitude=2.0,
        proximity=proximity,
        localisation=localisation,
    )
    assert mosque.display_name == expected
