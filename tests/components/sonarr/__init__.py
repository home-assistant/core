"""Tests for the Sonarr component."""
from socket import gaierror as SocketGIAError

from homeassistant.components.sonarr.const import (
    CONF_BASE_PATH,
    CONF_UPCOMING_DAYS,
    CONF_WANTED_MAX_ITEMS,
    DEFAULT_UPCOMING_DAYS,
    DEFAULT_WANTED_MAX_ITEMS,
    DOMAIN,
)
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
)
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

HOST = "192.168.1.189"
PORT = 8989
BASE_PATH = "/api"
API_KEY = "MOCK_API_KEY"

MOCK_SENSOR_CONFIG = {
    "platform": DOMAIN,
    "host": HOST,
    "api_key": API_KEY,
    "days": 3,
}

MOCK_USER_INPUT = {
    CONF_HOST: HOST,
    CONF_PORT: PORT,
    CONF_BASE_PATH: BASE_PATH,
    CONF_SSL: False,
    CONF_API_KEY: API_KEY,
}


def mock_connection(
    aioclient_mock: AiohttpClientMocker,
    host: str = HOST,
    port: str = PORT,
    base_path: str = BASE_PATH,
    error: bool = False,
    invalid_auth: bool = False,
    server_error: bool = False,
) -> None:
    """Mock Sonarr connection."""
    if error:
        mock_connection_error(
            aioclient_mock, host=host, port=port, base_path=base_path,
        )
        return

    if invalid_auth:
        mock_connection_invalid_auth(
            aioclient_mock, host=host, port=port, base_path=base_path,
        )
        return

    if server_error:
        mock_connection_server_error(
            aioclient_mock, host=host, port=port, base_path=base_path,
        )
        return

    sonarr_url = f"http://{host}:{port}{base_path}"

    aioclient_mock.get(
        f"{sonarr_url}/system/status",
        text=load_fixture(f"sonarr/system-status.json"),
        headers={"Content-Type": "application/json"},
    )

    aioclient_mock.get(
        f"{sonarr_url}/diskspace",
        text=load_fixture(f"sonarr/diskspace.json"),
        headers={"Content-Type": "application/json"},
    )

    aioclient_mock.get(
        f"{sonarr_url}/calendar",
        text=load_fixture(f"sonarr/calendar.json"),
        headers={"Content-Type": "application/json"},
    )

    aioclient_mock.get(
        f"{sonarr_url}/command",
        text=load_fixture(f"sonarr/command.json"),
        headers={"Content-Type": "application/json"},
    )

    aioclient_mock.get(
        f"{sonarr_url}/queue",
        text=load_fixture(f"sonarr/queue.json"),
        headers={"Content-Type": "application/json"},
    )

    aioclient_mock.get(
        f"{sonarr_url}/series",
        text=load_fixture(f"sonarr/series.json"),
        headers={"Content-Type": "application/json"},
    )

    aioclient_mock.get(
        f"{sonarr_url}/wanted/missing",
        text=load_fixture(f"sonarr/wanted-missing.json"),
        headers={"Content-Type": "application/json"},
    )


def mock_connection_error(
    aioclient_mock: AiohttpClientMocker,
    host: str = HOST,
    port: str = PORT,
    base_path: str = BASE_PATH,
) -> None:
    """Mock Sonarr connection errors."""
    sonarr_url = f"http://{host}:{port}{base_path}"

    aioclient_mock.get(f"{sonarr_url}/system/status", exc=SocketGIAError)
    aioclient_mock.get(f"{sonarr_url}/diskspace", exc=SocketGIAError)
    aioclient_mock.get(f"{sonarr_url}/calendar", exc=SocketGIAError)
    aioclient_mock.get(f"{sonarr_url}/command", exc=SocketGIAError)
    aioclient_mock.get(f"{sonarr_url}/queue", exc=SocketGIAError)
    aioclient_mock.get(f"{sonarr_url}/series", exc=SocketGIAError)
    aioclient_mock.get(f"{sonarr_url}/missing/wanted", exc=SocketGIAError)


def mock_connection_invalid_auth(
    aioclient_mock: AiohttpClientMocker,
    host: str = HOST,
    port: str = PORT,
    base_path: str = BASE_PATH,
) -> None:
    """Mock Sonarr invalid auth errors."""
    sonarr_url = f"http://{host}:{port}{base_path}"

    aioclient_mock.get(f"{sonarr_url}/system/status", status=403)
    aioclient_mock.get(f"{sonarr_url}/diskspace", status=403)
    aioclient_mock.get(f"{sonarr_url}/calendar", status=403)
    aioclient_mock.get(f"{sonarr_url}/command", status=403)
    aioclient_mock.get(f"{sonarr_url}/queue", status=403)
    aioclient_mock.get(f"{sonarr_url}/series", status=403)
    aioclient_mock.get(f"{sonarr_url}/missing/wanted", status=403)


def mock_connection_server_error(
    aioclient_mock: AiohttpClientMocker,
    host: str = HOST,
    port: str = PORT,
    base_path: str = BASE_PATH,
) -> None:
    """Mock Sonarr server errors."""
    sonarr_url = f"http://{host}:{port}{base_path}"

    aioclient_mock.get(f"{sonarr_url}/system/status", status=500)
    aioclient_mock.get(f"{sonarr_url}/diskspace", status=500)
    aioclient_mock.get(f"{sonarr_url}/calendar", status=500)
    aioclient_mock.get(f"{sonarr_url}/command", status=500)
    aioclient_mock.get(f"{sonarr_url}/queue", status=500)
    aioclient_mock.get(f"{sonarr_url}/series", status=500)
    aioclient_mock.get(f"{sonarr_url}/missing/wanted", status=500)


async def setup_integration(
    hass: HomeAssistantType,
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
) -> MockConfigEntry:
    """Set up the Sonarr integration in Home Assistant."""
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
            CONF_UPCOMING_DAYS: DEFAULT_UPCOMING_DAYS,
            CONF_WANTED_MAX_ITEMS: DEFAULT_WANTED_MAX_ITEMS,
        },
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

    return entry
