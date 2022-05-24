"""Test the Motion Blinds config flow."""
from unittest.mock import Mock

import pytest
from motionblinds import BlindType



async def test_device_name(hass):
    """test_device_name."""
    blind = Mock()
    blind.blind_type = BlindType.RollerBlind
    blind.mac = TEST_MAC
    assert device_name(blind) == "bla"