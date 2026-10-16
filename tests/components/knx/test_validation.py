"""Test KNX validation helpers."""

import probatio
import pytest
from xknx.telegram import IndividualAddress

from homeassistant.components.knx.validation import individual_address_validator


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1.1.5", IndividualAddress("1.1.5")),
        (" 15.15.255 ", IndividualAddress("15.15.255")),
        (4357, IndividualAddress("1.1.5")),
    ],
)
def test_individual_address_validator(
    value: str | int, expected: IndividualAddress
) -> None:
    """Test valid individual addresses are parsed."""
    assert individual_address_validator(value) == expected


@pytest.mark.parametrize("value", ["1/1/5", "1.1", "16.0.1", "1.1.256", "", 0])
def test_individual_address_validator_invalid(value: str | int) -> None:
    """Test invalid individual addresses are rejected."""
    with pytest.raises(probatio.Invalid):
        individual_address_validator(value)
