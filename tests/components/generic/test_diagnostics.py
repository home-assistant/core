"""Test generic (IP camera) diagnostics."""
from homeassistant.components.diagnostics import REDACTED

from tests.components.diagnostics import get_diagnostics_for_config_entry


async def test_entry_diagnostics(hass, hass_client, setup_entry):
    """Test config entry diagnostics."""

    assert await get_diagnostics_for_config_entry(hass, hass_client, setup_entry) == {
        "title": "Test Camera",
        "data": {},
        "options": {
            "still_image_url": "http://****:****@example.com/****?****=****",
            "stream_source": "http://****:****@example.com/****",
            "username": REDACTED,
            "password": REDACTED,
            "limit_refetch_to_url_change": False,
            "authentication": "basic",
            "framerate": 2.0,
            "verify_ssl": True,
            "content_type": "image/jpeg",
        },
    }
