"""Test the ENGIE Belgium coordinator helpers."""

from aioengiebelgium import bare_ean
import pytest

from homeassistant.components.engie_be.coordinator import lookup_by_ean

from .conftest import ELECTRICITY_EAN_2, OFFTAKE_INJECTION_EAN


@pytest.mark.parametrize(
    ("key", "lookup", "expected"),
    [
        pytest.param(
            OFFTAKE_INJECTION_EAN, OFFTAKE_INJECTION_EAN, True, id="exact_key"
        ),
        pytest.param(
            OFFTAKE_INJECTION_EAN,
            bare_ean(OFFTAKE_INJECTION_EAN),
            True,
            id="bare_lookup_into_suffixed_key",
        ),
        pytest.param(
            bare_ean(OFFTAKE_INJECTION_EAN),
            OFFTAKE_INJECTION_EAN,
            True,
            id="suffixed_lookup_into_bare_key",
        ),
        pytest.param(OFFTAKE_INJECTION_EAN, ELECTRICITY_EAN_2, False, id="miss"),
    ],
)
def test_lookup_by_ean_accepts_bare_and_suffixed_keys(
    key: str, lookup: str, expected: bool
) -> None:
    """Test the EAN lookup resolves bare and suffixed keys in both directions."""
    value = object()
    assert (lookup_by_ean({key: value}, lookup) is value) is expected


def test_lookup_by_ean_without_data_returns_none() -> None:
    """Test the EAN lookup returns None when there is no data."""
    assert lookup_by_ean(None, OFFTAKE_INJECTION_EAN) is None
