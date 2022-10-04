"""Tests for the Lidarr component."""
from http import HTTPStatus

from aiohttp.client_exceptions import ClientError
from aiopyarr.lidarr_client import LidarrClient

from homeassistant.components.lidarr.const import DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_URL,
    CONF_VERIFY_SSL,
    CONTENT_TYPE_JSON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

URL = "http://127.0.0.1:8668"
API_KEY = "1234567890abcdef1234567890abcdef"
client = LidarrClient(session=async_get_clientsession, api_token=API_KEY, url=URL)
API_URL = f"{URL}/api/{client._host.api_ver}"

MOCK_INPUT = {CONF_URL: URL, CONF_VERIFY_SSL: False}

CONF_DATA = MOCK_INPUT | {CONF_API_KEY: API_KEY}


def mock_connection(
    aioclient_mock: AiohttpClientMocker,
    url: str = API_URL,
    error: bool = False,
    cannot_connect: bool = False,
    invalid_auth: bool = False,
    windows: bool = False,
) -> None:
    """Mock lidarr connection."""

    if cannot_connect:
        mock_connection_error(
            aioclient_mock,
            url=url,
            status=HTTPStatus.INTERNAL_SERVER_ERROR,
        )
        return

    if invalid_auth:
        mock_connection_error(
            aioclient_mock,
            url=url,
            status=HTTPStatus.UNAUTHORIZED,
        )
        return

    if error:
        mock_connection_error(
            aioclient_mock,
            url=url,
        )
        return

    aioclient_mock.get(
        f"{url}/system/status",
        text=load_fixture("lidarr/system-status.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        f"{url}/queue",
        text=load_fixture("lidarr/queue.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        f"{url}/wanted/missing",
        text=load_fixture("lidarr/wanted-missing.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    if windows:
        aioclient_mock.get(
            f"{url}/rootfolder",
            text=load_fixture("lidarr/rootfolder-windows.json"),
            headers={"Content-Type": CONTENT_TYPE_JSON},
        )
    else:
        aioclient_mock.get(
            f"{url}/rootfolder",
            text=load_fixture("lidarr/rootfolder-linux.json"),
            headers={"Content-Type": CONTENT_TYPE_JSON},
        )


def mock_connection_error(
    aioclient_mock: AiohttpClientMocker,
    url: str = API_URL,
    status: HTTPStatus | None = None,
) -> None:
    """Mock lidarr connection errors."""
    if status:
        aioclient_mock.get(f"{url}/queue", status=status)
        aioclient_mock.get(f"{url}/rootfolder", status=status)
        aioclient_mock.get(f"{url}/system/status", status=status)
        aioclient_mock.get(f"{url}/wanted/missing", status=status)
        return
    aioclient_mock.get(f"{url}/queue", exc=ClientError)
    aioclient_mock.get(f"{url}/rootfolder", exc=ClientError)
    aioclient_mock.get(f"{url}/system/status", exc=ClientError)
    aioclient_mock.get(f"{url}/wanted/missing", exc=ClientError)


async def setup_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    url: str = API_URL,
    skip_entry_setup: bool = False,
    connection_error: bool = False,
    invalid_auth: bool = False,
    windows: bool = False,
) -> MockConfigEntry:
    """Set up the lidarr integration in Home Assistant."""
    entry = create_entry(hass)
    mock_connection(
        aioclient_mock,
        url=url,
        error=connection_error,
        invalid_auth=invalid_auth,
        windows=windows,
    )

    if not skip_entry_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert await async_setup_component(hass, DOMAIN, {})

    return entry


def create_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create Lidarr entry in Home Assistant."""
    entry = MockConfigEntry(domain=DOMAIN, data=CONF_DATA)
    entry.add_to_hass(hass)
    return entry
