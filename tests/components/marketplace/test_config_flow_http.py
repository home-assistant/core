"""Exercise the device flow with real response header parsing."""

from collections.abc import Callable, Generator
from unittest.mock import patch

from aiogithubapi import GitHubDeviceAPI
from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer
import pytest
from pytest_homeassistant.common import MockConfigEntry
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
def aioclient_mock() -> AiohttpClientMocker:
    """Keep the real Home Assistant session and HTTP parser for these tests."""
    return AiohttpClientMocker()


@pytest.fixture
async def device_server(
    aiohttp_server: Callable[[], TestServer],
    registration_header_size: int,
    activation_header_size: int,
) -> TestServer:
    """Serve only synthetic device registration and activation responses."""

    async def register(request: web.Request) -> web.Response:
        return web.json_response(
            {
                "device_code": "synthetic-device-code",
                "user_code": "TEST-CODE",
                "verification_uri": "https://example.invalid/device",
                "expires_in": 600,
                "interval": 1,
            },
            headers={"Content-Security-Policy": "x" * registration_header_size},
        )

    async def activate(request: web.Request) -> web.Response:
        return web.json_response(
            {"access_token": "synthetic-token", "token_type": "bearer", "scope": ""},
            headers={"Content-Security-Policy": "x" * activation_header_size},
        )

    app = web.Application()
    app.router.add_post("/login/device/code", register)
    app.router.add_post("/login/oauth/access_token", activate)
    return await aiohttp_server(app)


@pytest.fixture
def local_device_api(device_server: TestServer) -> Generator[None]:
    """Point the real GitHub client at the loopback fixture server."""

    def create_device_api(
        client_id: str, session: ClientSession, client_name: str
    ) -> GitHubDeviceAPI:
        return GitHubDeviceAPI(
            client_id=client_id,
            session=session,
            client_name=client_name,
            base_url=str(device_server.make_url("/")).rstrip("/"),
        )

    with patch(
        "homeassistant.components.marketplace.config_flow.GitHubDeviceAPI",
        side_effect=create_device_api,
    ):
        yield


@pytest.mark.usefixtures("socket_enabled", "mock_setup_entry", "local_device_api")
@pytest.mark.parametrize(
    ("registration_header_size", "activation_header_size"),
    [
        pytest.param(1024, 1024, id="small"),
        pytest.param(9217, 1024, id="large-registration"),
        pytest.param(1024, 9217, id="large-activation"),
        pytest.param(65000, 65000, id="within-bounded-limit"),
    ],
)
async def test_device_flow_response_headers(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Register and activate with headers larger than aiohttp's default."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    assert result["step_id"] == "device"
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_TOKEN] == "synthetic-token"


@pytest.mark.usefixtures("socket_enabled", "mock_setup_entry", "local_device_api")
@pytest.mark.parametrize("registration_header_size", [65537])
@pytest.mark.parametrize("activation_header_size", [1024])
async def test_registration_response_header_limit(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Continue rejecting registration headers beyond the bounded limit."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "could_not_register"


@pytest.mark.usefixtures("socket_enabled", "mock_setup_entry", "local_device_api")
@pytest.mark.parametrize("registration_header_size", [1024])
@pytest.mark.parametrize("activation_header_size", [65537])
async def test_activation_response_header_limit(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Continue rejecting activation headers beyond the bounded limit."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.SHOW_PROGRESS
    await hass.async_block_till_done()
    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "activation_failed"
