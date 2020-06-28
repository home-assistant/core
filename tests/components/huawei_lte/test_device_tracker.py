"""Huawei LTE device tracker tests."""

import pytest

from homeassistant.components.huawei_lte import device_tracker


@pytest.mark.parametrize(
    ("value", "expected"),
    (
        ("HTTP", "http"),
        ("ID", "id"),
        ("IPAddress", "ip_address"),
        ("HTTPResponse", "http_response"),
        ("foo_bar", "foo_bar"),
    ),
)
def test_better_snakecase(value, expected):
    """Test that better snakecase works better."""
    assert device_tracker._better_snakecase(value) == expected
