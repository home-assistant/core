"""Test the zerproc config flow."""
from asynctest import patch

from homeassistant.components.zerproc.config_flow import _async_has_devices


class MockException(Exception):
    """Mock exception class."""


async def test_has_devices(hass):
    """Test we get the form."""
    with patch(
        "homeassistant.components.zerproc.config_flow.pyzerproc.discover",
        return_value=[],
    ):
        assert await _async_has_devices(hass) is False
    with patch(
        "homeassistant.components.zerproc.config_flow.pyzerproc.discover",
        return_value=["Light1", "Light2"],
    ):
        assert await _async_has_devices(hass) is True
    with patch(
        "homeassistant.components.zerproc.config_flow.pyzerproc.discover",
        side_effect=MockException("TEST"),
    ), patch(
        "homeassistant.components.zerproc.config_flow.pyzerproc.ZerprocException",
        new=MockException,
    ):
        assert await _async_has_devices(hass) is False
