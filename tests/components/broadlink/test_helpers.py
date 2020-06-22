"""Tests for Broadlink helper functions."""
from homeassistant.components.broadlink.helpers import data_packet


async def test_padding(hass):
    """Verify that non padding strings are allowed."""
    assert data_packet("Jg") == b"&"
    assert data_packet("Jg=") == b"&"
    assert data_packet("Jg==") == b"&"
