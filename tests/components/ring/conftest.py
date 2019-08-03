"""Configuration for HEOS tests."""
import requests_mock
import pytest
from homeassistant.components.ring import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, CONF_SCAN_INTERVAL
from tests.common import MockConfigEntry
from homeassistant.setup import async_setup_component
from tests.common import load_fixture


@pytest.fixture(name="config_entry")
def config_entry_fixture():
    """Create a mock ring config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "foo", CONF_PASSWORD: "bar", CONF_SCAN_INTERVAL: 1000},
        title="Ring",
    )


@pytest.fixture(name="requests_mock")
def requests_mock_fixture():
    """Fixture to provide a requests mocker."""
    with requests_mock.mock() as mock:
        # Note all devices have an id of 987652, but a different device_id.
        # the device_id is used as our unique_id, but the id is what is sent
        # to the APIs, which is why every mock uses that id.

        # Mocks the response for authenticating
        mock.post(
            "https://oauth.ring.com/oauth/token", text=load_fixture("ring_oauth.json")
        )
        # Mocks the response for getting the login session
        mock.post(
            "https://api.ring.com/clients_api/session",
            text=load_fixture("ring_session.json"),
        )
        # Mocks the response for getting all the devices
        mock.get(
            "https://api.ring.com/clients_api/ring_devices",
            text=load_fixture("ring_devices.json"),
        )
        # Mocks the response for getting the history of a device
        mock.get(
            "https://api.ring.com/clients_api/doorbots/987652/history",
            text=load_fixture("ring_doorbots.json"),
        )
        # Mocks the response for getting the health of a device
        mock.get(
            "https://api.ring.com/clients_api/doorbots/987652/health",
            text=load_fixture("ring_doorboot_health_attrs.json"),
        )
        # Mocks the response for getting a chimes health
        mock.get(
            "https://api.ring.com/clients_api/chimes/999999/health",
            text=load_fixture("ring_chime_health_attrs.json"),
        )

        yield mock


async def setup_platform(hass, platform):
    """Set up the ring platform and prerequisites."""
    config = {
        DOMAIN: {CONF_USERNAME: "foo", CONF_PASSWORD: "bar", CONF_SCAN_INTERVAL: 1000},
        platform: {"platform": DOMAIN},
    }
    assert await async_setup_component(hass, platform, config)
    await hass.async_block_till_done()
