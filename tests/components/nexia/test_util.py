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
