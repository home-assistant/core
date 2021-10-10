"""Tests for the Tautulli integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.tautulli.const import CONF_MONITORED_USERS, DOMAIN
from homeassistant.const import (
    CONF_API_KEY,
    CONF_HOST,
    CONF_PATH,
    CONF_PORT,
    CONF_SSL,
    CONF_VERIFY_SSL,
    CONTENT_TYPE_JSON,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, load_fixture
from tests.test_util.aiohttp import AiohttpClientMocker

API_KEY = "abcd"
HOST = "1.2.3.4"
NAME = "Tautulli"
PORT = "8181"
PATH = "/test"
SSL = False
VERIFY_SSL = True
UNIQUE_ID = "1234567890abcdef1234567890abcdef12345678"

CONF_DATA = {
    CONF_API_KEY: API_KEY,
    CONF_HOST: HOST,
    CONF_PORT: PORT,
    CONF_PATH: PATH,
    CONF_SSL: SSL,
}
CONF_DATA_ADVANCED = {
    CONF_API_KEY: API_KEY,
    CONF_HOST: HOST,
    CONF_PORT: PORT,
    CONF_PATH: PATH,
    CONF_SSL: SSL,
    CONF_VERIFY_SSL: VERIFY_SSL,
}

DEFAULT_USERS = [{11111111: {"enabled": False}, 22222222: {"enabled": False}}]
SELECTED_USERNAMES = ["user1"]


async def _create_mocked_tautulli():
    mocked_tautulli = AsyncMock()
    mocked_tautulli.pms_identifier = UNIQUE_ID
    return mocked_tautulli


def _patch_config_flow_tautulli(mocked_tautulli):
    return patch(
        "homeassistant.components.tautulli.config_flow.PyTautulli.async_get_server_info",
        return_value=mocked_tautulli,
    )


def mock_connection(
    aioclient_mock: AiohttpClientMocker,
    host: str = HOST,
    port: str = PORT,
    path: str = PATH,
    invalid_auth: bool = False,
) -> None:
    """Mock Tautulli connection."""
    url = f"http://{host}:{port}{path}/api/v2?apikey={API_KEY}"

    if invalid_auth:
        aioclient_mock.get(
            f"{url}&cmd=get_activity",
            text=load_fixture("tautulli/get_activity.json"),
            headers={"Content-Type": CONTENT_TYPE_JSON},
        )
        return

    aioclient_mock.get(
        f"{url}&cmd=get_activity",
        text=load_fixture("tautulli/get_activity.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        f"{url}&cmd=get_home_stats",
        text=load_fixture("tautulli/get_home_stats.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )
    aioclient_mock.get(
        f"{url}&cmd=get_users",
        text=load_fixture("tautulli/get_users.json"),
        headers={"Content-Type": CONTENT_TYPE_JSON},
    )


async def setup_integration(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    host: str = HOST,
    port: str = PORT,
    path: str = PATH,
    api_key: str = API_KEY,
    unique_id: str = None,
    skip_entry_setup: bool = False,
    invalid_auth: bool = False,
) -> MockConfigEntry:
    """Set up the Tautulli integration in Home Assistant."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=unique_id,
        data={
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_PATH: path,
            CONF_SSL: SSL,
            CONF_VERIFY_SSL: VERIFY_SSL,
            CONF_API_KEY: api_key,
        },
        options={
            CONF_MONITORED_USERS: DEFAULT_USERS,
        },
    )

    entry.add_to_hass(hass)

    mock_connection(
        aioclient_mock,
        host=host,
        port=port,
        path=path,
        invalid_auth=invalid_auth,
    )

    if not skip_entry_setup:
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry
