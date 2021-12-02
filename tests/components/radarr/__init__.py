"""Tests for the Radarr component."""
from http import HTTPStatus
from unittest.mock import patch

from aiohttp.client_exceptions import ClientError

from homeassistant.components.radarr.const import (
    CONF_BASE_PATH,
    CONF_UPCOMING_DAYS,
    CONF_URLBASE,
    DEFAULT_SSL,
    DEFAULT_UPCOMING_DAYS,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
    CONTENT_TYPE_JSON,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

HOST = "192.168.1.189"
PORT = 7878
BASE_PATH = ""
API_KEY = "MOCK_API_KEY"

MOCK_REAUTH_INPUT = {CONF_API_KEY: "test-api-key-reauth"}

MOCK_USER_INPUT = {
    CONF_HOST: HOST,
    CONF_PORT: PORT,
    CONF_BASE_PATH: BASE_PATH,
    CONF_SSL: DEFAULT_SSL,
    CONF_API_KEY: API_KEY,
}

CONF_IMPORT_DATA = {
    CONF_API_KEY: API_KEY,
    CONF_HOST: "1.2.3.4",
    CONF_MONITORED_CONDITIONS: ["Stream count"],
    CONF_PORT: "7887",
    CONF_URLBASE: "/test",
    CONF_SSL: DEFAULT_SSL,
}

CONF_DATA = {
    CONF_HOST: "1.2.3.4",
    CONF_PORT: "7887",
    CONF_BASE_PATH: "/test",
    CONF_SSL: DEFAULT_SSL,
    CONF_API_KEY: API_KEY,
    CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
}


def mock_connection(
    aioclient_mock: AiohttpClientMocker,
    host: str = HOST,
    port: str = PORT,
    base_path: str = "",
    ssl: str = DEFAULT_SSL,
    error: bool = False,
    invalid_auth: bool = False,
    server_error: bool = False,
) -> None:
    """Mock radarr connection."""
    if error:
        mock_connection_error(
            aioclient_mock,
            host=host,
            port=port,
            ssl=ssl,
            base_path=base_path,
        )
        return

    if invalid_auth:
        mock_connection_invalid_auth(
            aioclient_mock,
            host=host,
            port=port,
            ssl=ssl,
            base_path=base_path,
        )
        return

    if server_error:
        mock_connection_server_error(
            aioclient_mock,
            host=host,
            port=port,
            ssl=ssl,
            base_path=base_path,
        )
        return

    radarr_url = f"http{'s' if ssl else ''}://{host}:{port}{base_path}/api/v3"

    aioclient_mock.get(
        f"{radarr_url}/system/status",
        text=load_fixture("radarr/system-status.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"{radarr_url}/diskspace",
        text=load_fixture("radarr/diskspace.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"{radarr_url}/calendar",
        text=load_fixture("radarr/calendar.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"{radarr_url}/command",
        text=load_fixture("radarr/command.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"{radarr_url}/movie",
        text=load_fixture("radarr/movie.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )

    aioclient_mock.get(
        f"{radarr_url}/rootfolder",
        text=load_fixture("radarr/rootfolder.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )


def mock_connection_error(
    aioclient_mock: AiohttpClientMocker,
    host: str = HOST,
    port: str = PORT,
    base_path: str = "",
    ssl: bool = DEFAULT_SSL,
) -> None:
    """Mock radarr connection errors."""
    radarr_url = f"http{'s' if ssl else ''}://{host}:{port}{base_path}/api/v3"

    aioclient_mock.get(f"{radarr_url}/system/status", exc=ClientError)


def mock_connection_invalid_auth(
    aioclient_mock: AiohttpClientMocker,
    host: str = HOST,
    port: str = PORT,
    base_path: str = "",
    ssl: bool = DEFAULT_SSL,
) -> None:
    """Mock radarr invalid auth errors."""
    radarr_url = f"http{'s' if ssl else ''}://{host}:{port}{base_path}/api/v3"

    aioclient_mock.get(f"{radarr_url}/system/status", status=HTTPStatus.UNAUTHORIZED)
    aioclient_mock.get(f"{radarr_url}/diskspace", status=HTTPStatus.UNAUTHORIZED)
    aioclient_mock.get(f"{radarr_url}/calendar", status=HTTPStatus.UNAUTHORIZED)
    aioclient_mock.get(f"{radarr_url}/command", status=HTTPStatus.UNAUTHORIZED)
    aioclient_mock.get(f"{radarr_url}/movie", status=HTTPStatus.UNAUTHORIZED)
    aioclient_mock.get(f"{radarr_url}/rootfolder", status=HTTPStatus.UNAUTHORIZED)


def mock_connection_server_error(
    aioclient_mock: AiohttpClientMocker,
    host: str = HOST,
    port: str = PORT,
    base_path: str = "",
    ssl: bool = DEFAULT_SSL,
) -> None:
    """Mock radarr server errors."""
    radarr_url = f"http{'s' if ssl else ''}://{host}:{port}{base_path}/api/v3"

    aioclient_mock.get(
        f"{radarr_url}/system/status", status=HTTPStatus.INTERNAL_SERVER_ERROR
    )
    aioclient_mock.get(
        f"{radarr_url}/diskspace", status=HTTPStatus.INTERNAL_SERVER_ERROR
    )
    aioclient_mock.get(
        f"{radarr_url}/calendar", status=HTTPStatus.INTERNAL_SERVER_ERROR
    )
    aioclient_mock.get(f"{radarr_url}/command", status=HTTPStatus.INTERNAL_SERVER_ERROR)
    aioclient_mock.get(f"{radarr_url}/movie", status=HTTPStatus.INTERNAL_SERVER_ERROR)
    aioclient_mock.get(
        f"{radarr_url}/rootfolder", status=HTTPStatus.INTERNAL_SERVER_ERROR
    )


async def setup_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    host: str = HOST,
    port: str = PORT,
    base_path: str = BASE_PATH,
    api_key: str = API_KEY,
    unique_id: str = None,
    skip_entry_setup: bool = False,
    connection_error: bool = False,
    invalid_auth: bool = False,
    server_error: bool = False,
    no_options: bool = False,
) -> MockConfigEntry:
    """Set up the radarr integration in Home Assistant."""
    if no_options:
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=unique_id,
            data={
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_BASE_PATH: base_path,
                CONF_SSL: False,
                CONF_VERIFY_SSL: False,
                CONF_API_KEY: api_key,
            },
        )
    else:
        entry = MockConfigEntry(
            domain=DOMAIN,
            unique_id=unique_id,
            data={
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_BASE_PATH: base_path,
                CONF_SSL: False,
                CONF_VERIFY_SSL: False,
                CONF_API_KEY: api_key,
            },
            options={CONF_UPCOMING_DAYS: DEFAULT_UPCOMING_DAYS},
        )

    entry.add_to_hass(hass)

    mock_connection(
        aioclient_mock,
        host=host,
        port=port,
        base_path=base_path,
        error=connection_error,
        invalid_auth=invalid_auth,
        server_error=server_error,
    )

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


def patch_radarr():
    """Patch radarr api."""
    return patch("homeassistant.components.radarr.RadarrClient.async_get_system_status")


def create_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create Efergy entry in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_BASE_PATH: BASE_PATH,
            CONF_SSL: False,
            CONF_VERIFY_SSL: False,
            CONF_API_KEY: API_KEY,
        },
        options={CONF_UPCOMING_DAYS: DEFAULT_UPCOMING_DAYS},
    )

    entry.add_to_hass(hass)
    return entry
