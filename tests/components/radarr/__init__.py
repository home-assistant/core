"""Tests for the Radarr component."""

from http import HTTPStatus
from unittest.mock import patch

from aiohttp.client_exceptions import ClientError

from homeassistant.components.radarr.const import DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_URL,
    CONF_VERIFY_SSL,
    CONTENT_TYPE_JSON,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

URL = "http://192.168.1.189:7887/test"
API_KEY = "MOCK_API_KEY"

MOCK_REAUTH_INPUT = {CONF_API_KEY: "test-api-key-reauth"}

MOCK_USER_INPUT = {
    CONF_URL: URL,
    CONF_API_KEY: API_KEY,
    CONF_VERIFY_SSL: False,
}

CONF_DATA = {
    CONF_URL: URL,
    CONF_API_KEY: API_KEY,
    CONF_VERIFY_SSL: False,
}


def mock_connection(
    aioclient_mock: AiohttpClientMocker,
    url: str = URL,
    error: bool = False,
    invalid_auth: bool = False,
    windows: bool = False,
    single_return: bool = False,
) -> None:
    """Mock radarr connection."""
    if error:
        mock_connection_error(
            aioclient_mock,
            url=url,
        )
        return

    if invalid_auth:
        mock_connection_invalid_auth(
            aioclient_mock,
            url=url,
        )
        return

    aioclient_mock.get(
        f"{url}/api/v3/system/status",
        text=load_fixture("radarr/system-status.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"{url}/api/v3/command",
        text=load_fixture("radarr/command.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"{url}/api/v3/health",
        text=load_fixture("radarr/health.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"{url}/api/v3/queue",
        text=load_fixture("radarr/queue.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    root_folder_fixture = "rootfolder-linux"

    if windows:
        root_folder_fixture = "rootfolder-windows"

    if single_return:
        root_folder_fixture = f"single-{root_folder_fixture}"

    aioclient_mock.get(
        f"{url}/api/v3/rootfolder",
        text=load_fixture(f"radarr/{root_folder_fixture}.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"{url}/api/v3/movie",
        text=load_fixture("radarr/movie.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )


def mock_calendar(
    aioclient_mock: AiohttpClientMocker,
    url: str = URL,
) -> None:
    """Mock radarr connection."""
    aioclient_mock.get(
        f"{url}/api/v3/calendar",
        text=load_fixture("radarr/calendar.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )


def mock_connection_error(
    aioclient_mock: AiohttpClientMocker,
    url: str = URL,
) -> None:
    """Mock radarr connection errors."""
    aioclient_mock.get(f"{url}/api/v3/system/status", exc=ClientError)


def mock_connection_invalid_auth(
    aioclient_mock: AiohttpClientMocker,
    url: str = URL,
) -> None:
    """Mock radarr invalid auth errors."""
    aioclient_mock.get(f"{url}/api/v3/command", status=HTTPStatus.UNAUTHORIZED)
    aioclient_mock.get(f"{url}/api/v3/movie", status=HTTPStatus.UNAUTHORIZED)
    aioclient_mock.get(f"{url}/api/v3/queue", status=HTTPStatus.UNAUTHORIZED)
    aioclient_mock.get(f"{url}/api/v3/rootfolder", status=HTTPStatus.UNAUTHORIZED)
    aioclient_mock.get(f"{url}/api/v3/system/status", status=HTTPStatus.UNAUTHORIZED)
    aioclient_mock.get(f"{url}/api/v3/calendar", status=HTTPStatus.UNAUTHORIZED)


def mock_connection_server_error(
    aioclient_mock: AiohttpClientMocker,
    url: str = URL,
) -> None:
    """Mock radarr server errors."""
    aioclient_mock.get(f"{url}/api/v3/command", status=HTTPStatus.INTERNAL_SERVER_ERROR)
    aioclient_mock.get(f"{url}/api/v3/movie", status=HTTPStatus.INTERNAL_SERVER_ERROR)
    aioclient_mock.get(f"{url}/api/v3/queue", status=HTTPStatus.INTERNAL_SERVER_ERROR)
    aioclient_mock.get(
        f"{url}/api/v3/rootfolder", status=HTTPStatus.INTERNAL_SERVER_ERROR
    )
    aioclient_mock.get(
        f"{url}/api/v3/system/status", status=HTTPStatus.INTERNAL_SERVER_ERROR
    )
    aioclient_mock.get(
        f"{url}/api/v3/calendar", status=HTTPStatus.INTERNAL_SERVER_ERROR
    )


async def setup_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    url: str = URL,
    api_key: str = API_KEY,
    unique_id: str | None = None,
    skip_entry_setup: bool = False,
    connection_error: bool = False,
    invalid_auth: bool = False,
    windows: bool = False,
    single_return: bool = False,
) -> MockConfigEntry:
    """Set up the radarr integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        data={
            CONF_URL: url,
            CONF_API_KEY: api_key,
            CONF_VERIFY_SSL: False,
        },
    )

    entry.add_to_hass(hass)

    mock_connection(
        aioclient_mock,
        url=url,
        error=connection_error,
        invalid_auth=invalid_auth,
        windows=windows,
        single_return=single_return,
    )

    mock_calendar(aioclient_mock, url)

    if not skip_entry_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert await async_setup_component(hass, DOMAIN, {})

    return entry


def patch_async_setup_entry(return_value=True):
    """Patch the async entry setup of radarr."""
    return patch(
        "homeassistant.components.radarr.async_setup_entry",
        return_value=return_value,
    )


def create_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create Radarr entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_URL: URL,
            CONF_API_KEY: API_KEY,
            CONF_VERIFY_SSL: False,
        },
    )

    entry.add_to_hass(hass)
    return entry
