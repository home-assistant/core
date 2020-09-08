"""The sensor tests for the nexia platform."""


from homeassistant.components.nexia import util
from homeassistant.const import HTTP_FORBIDDEN, HTTP_NOT_FOUND, HTTP_UNAUTHORIZED


async def test_is_invalid_auth_code():
    """Test for invalid auth."""

    assert util.is_invalid_auth_code(HTTP_UNAUTHORIZED) is True
    assert util.is_invalid_auth_code(HTTP_FORBIDDEN) is True
    assert util.is_invalid_auth_code(HTTP_NOT_FOUND) is False


async def test_percent_conv():
    """Test percentage conversion."""

    assert util.percent_conv(0.12) == 12.0
    assert util.percent_conv(0.123) == 12.3
