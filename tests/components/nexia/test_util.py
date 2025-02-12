"""The sensor tests for the nexia platform."""

from http import HTTPStatus

from homeassistant.components.nexia import util


async def test_is_invalid_auth_code() -> None:
    """Test for invalid auth."""

    assert util.is_invalid_auth_code(HTTPStatus.UNAUTHORIZED) is True
    assert util.is_invalid_auth_code(HTTPStatus.FORBIDDEN) is True
    assert util.is_invalid_auth_code(HTTPStatus.NOT_FOUND) is False


async def test_percent_conv() -> None:
    """Test percentage conversion."""

    assert util.percent_conv(0.12) == 12.0
    assert util.percent_conv(0.123) == 12.3


async def test_closest_value() -> None:
    """Test closest value."""

    assert util.closest_value((10, 35), 5, 18) == 20
    assert util.closest_value((10, 35), 5, 15) == 15
    assert util.closest_value((0, 100), 5, 89) == 90

    # Test edge cases
    assert util.closest_value((35, 65), 5, 15) == 35
    assert util.closest_value((10, 35), 5, 55) == 35
