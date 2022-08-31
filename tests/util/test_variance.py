"""Test variance method."""
from datetime import datetime, timedelta

import pytest

from homeassistant.util.variance import ignore_variance


@pytest.mark.parametrize(
    "value_1, value_2, variance, expected",
    [
        (1, 1, 1, 1),
        (1, 2, 2, 1),
        (1, 2, 0, 2),
        (2, 1, 0, 1),
        (
            datetime(2020, 1, 1, 0, 0),
            datetime(2020, 1, 2, 0, 0),
            timedelta(days=2),
            datetime(2020, 1, 1, 0, 0),
        ),
        (
            datetime(2020, 1, 2, 0, 0),
            datetime(2020, 1, 1, 0, 0),
            timedelta(days=2),
            datetime(2020, 1, 2, 0, 0),
        ),
        (
            datetime(2020, 1, 1, 0, 0),
            datetime(2020, 1, 2, 0, 0),
            timedelta(days=1),
            datetime(2020, 1, 2, 0, 0),
        ),
    ],
)
def test_ignore_variance(value_1, value_2, variance, expected):
    """Test ignore_variance."""
    with_ignore = ignore_variance(lambda x: x, variance)
    assert with_ignore(value_1) == value_1
    assert with_ignore(value_2) == expected
