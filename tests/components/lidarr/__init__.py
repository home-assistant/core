"""Tests for the Lidarr component."""
from aiopyarr.lidarr_client import LidarrClient

from homeassistant.components.lidarr.const import (
    CONF_MAX_RECORDS,
    DEFAULT_MAX_RECORDS,
    DEFAULT_URL,
    DOMAIN,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_URL,
    CONF_VERIFY_SSL,
    CONTENT_TYPE_JSON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

BASE_PATH = ""
API_KEY = "1234567890abcdef1234567890abcdef"
client = LidarrClient(
    session=async_get_clientsession, api_token=API_KEY, url=DEFAULT_URL
)
API_URL = f"{DEFAULT_URL}/api/{client._host.api_ver}"

MOCK_REAUTH_INPUT = {CONF_API_KEY: "new_key"}

MOCK_USER_INPUT = {
    CONF_URL: DEFAULT_URL,
    CONF_VERIFY_SSL: False,
}

CONF_DATA = {
    CONF_URL: DEFAULT_URL,
    CONF_API_KEY: API_KEY,
    CONF_VERIFY_SSL: False,
}


def mock_connection(
    aioclient_mock: AiohttpClientMocker,
    url: str = API_URL,
) -> None:
    """Mock lidarr connection."""
    aioclient_mock.get(
        f"{url}/system/status",
        text=load_fixture("lidarr/system-status.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"{url[:21]}/initialize.js",
        text=load_fixture("lidarr/initialize.js"),
        headers={"Content-Type": "application/javascript"},
    )


def create_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create Efergy entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONF_DATA,
        options={CONF_MAX_RECORDS: DEFAULT_MAX_RECORDS},
    )

    entry.add_to_hass(hass)
    return entry
