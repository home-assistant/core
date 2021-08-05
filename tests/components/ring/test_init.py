"""The tests for the Ring component."""
from datetime import timedelta

import homeassistant.components.ring as ring
from homeassistant.setup import async_setup_component

from tests.common import load_fixture

ATTRIBUTION = "Data provided by Ring.com"

VALID_CONFIG = {
    "ring": {"username": "foo", "password": "bar", "scan_interval": timedelta(10)}
}


async def test_setup(hass, requests_mock):
    """Test the setup."""
    await async_setup_component(hass, ring.DOMAIN, {})

    requests_mock.post(
        "https://oauth.ring.com/oauth/token", text=load_fixture("ring_oauth.json")
    )
    requests_mock.post(
        "https://api.ring.com/clients_api/session",
        text=load_fixture("ring_session.json"),
    )
    requests_mock.get(
        "https://api.ring.com/clients_api/ring_devices",
        text=load_fixture("ring_devices.json"),
    )
    requests_mock.get(
        "https://api.ring.com/clients_api/chimes/999999/health",
        text=load_fixture("ring_chime_health_attrs.json"),
    )
    requests_mock.get(
        "https://api.ring.com/clients_api/doorbots/987652/health",
        text=load_fixture("ring_doorboot_health_attrs.json"),
    )

    assert await ring.async_setup(hass, VALID_CONFIG)
