"""Test the Developer Credentials integration."""

from __future__ import annotations

from collections.abc import Callable, Generator
import logging
from typing import Any
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.application_credentials import (
    CONF_AUTH_DOMAIN,
    DEFAULT_IMPORT_NAME,
    DOMAIN,
    AuthImplementation,
    AuthorizationServer,
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.const import (
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_DOMAIN,
    CONF_NAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, mock_config_flow, mock_platform
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator, WebSocketGenerator

CLIENT_ID = "some-client-id"
CLIENT_SECRET = "some-client-secret"
DEVELOPER_CREDENTIAL = ClientCredential(CLIENT_ID, CLIENT_SECRET)
NAMED_CREDENTIAL = ClientCredential(CLIENT_ID, CLIENT_SECRET, "Name")
ID = "fake_integration_some_client_id"
AUTHORIZE_URL = "https://example.com/auth"
TOKEN_URL = "https://example.com/oauth2/v4/token"
REFRESH_TOKEN = "mock-refresh-token"
ACCESS_TOKEN = "mock-access-token"
NAME = "Name"

TEST_DOMAIN = "fake_integration"


@pytest.fixture
async def authorization_server() -> AuthorizationServer:
    """Fixture AuthorizationServer for mock application_credentials integration."""
    return AuthorizationServer(AUTHORIZE_URL, TOKEN_URL)


@pytest.fixture
async def config_credential() -> ClientCredential | None:
    """Fixture ClientCredential for mock application_credentials integration."""
    return None


@pytest.fixture
async def import_config_credential(
    hass: HomeAssistant, config_credential: ClientCredential
) -> None:
    """Fixture to import the yaml based credential."""
    await async_import_client_credential(hass, TEST_DOMAIN, config_credential)


async def setup_application_credentials_integration(
    hass: HomeAssistant,
    domain: str,
    authorization_server: AuthorizationServer,
) -> None:
    """Set up a fake application_credentials integration."""
    hass.config.components.add(domain)
    mock_platform_impl = Mock(
        async_get_authorization_server=AsyncMock(return_value=authorization_server),
    )
    del mock_platform_impl.async_get_auth_implementation  # return False on hasattr
    mock_platform(
        hass,
        f"{domain}.application_credentials",
        mock_platform_impl,
    )


@pytest.fixture(autouse=True)
async def mock_application_credentials_integration(
    hass: HomeAssistant,
    authorization_server: AuthorizationServer,
):
    """Mock a application_credentials integration."""
    with patch("homeassistant.loader.APPLICATION_CREDENTIALS", [TEST_DOMAIN]):
        assert await async_setup_component(hass, "application_credentials", {})
        await setup_application_credentials_integration(
            hass, TEST_DOMAIN, authorization_server
        )
        yield


class FakeConfigFlow(config_entry_oauth2_flow.AbstractOAuth2FlowHandler):
    """Config flow used during tests."""

    DOMAIN = TEST_DOMAIN

    @property
    def logger(self) -> logging.Logger:
        """Return logger."""
        return logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def config_flow_handler(
    hass: HomeAssistant, current_request_with_host: Any
) -> Generator[FakeConfigFlow, None, None]:
    """Fixture for a test config flow."""
    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")
    with mock_config_flow(TEST_DOMAIN, FakeConfigFlow):
        yield


class OAuthFixture:
    """Fixture to facilitate testing an OAuth flow."""

    def __init__(self, hass, hass_client, aioclient_mock):
        """Initialize OAuthFixture."""
        self.hass = hass
        self.hass_client = hass_client
        self.aioclient_mock = aioclient_mock
        self.client_id = CLIENT_ID
        self.title = CLIENT_ID

    async def complete_external_step(
        self, result: data_entry_flow.FlowResult
    ) -> data_entry_flow.FlowResult:
        """Fixture method to complete the OAuth flow and return the completed result."""
        client = await self.hass_client()
        state = config_entry_oauth2_flow._encode_jwt(
            self.hass,
            {
                "flow_id": result["flow_id"],
                "redirect_uri": "https://example.com/auth/external/callback",
            },
        )
        assert result["url"] == (
            f"{AUTHORIZE_URL}?response_type=code&client_id={self.client_id}"
            "&redirect_uri=https://example.com/auth/external/callback"
            f"&state={state}"
        )
        resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
        assert resp.status == 200
        assert resp.headers["content-type"] == "text/html; charset=utf-8"

        self.aioclient_mock.post(
            TOKEN_URL,
            json={
                "refresh_token": REFRESH_TOKEN,
                "access_token": ACCESS_TOKEN,
                "type": "bearer",
                "expires_in": 60,
            },
        )

        result = await self.hass.config_entries.flow.async_configure(result["flow_id"])
        assert result.get("type") is FlowResultType.CREATE_ENTRY
        assert result.get("title") == self.title
        assert "data" in result
        assert "token" in result["data"]
        return result


@pytest.fixture
async def oauth_fixture(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: Any,
) -> OAuthFixture:
    """Fixture for testing the OAuth flow."""
    return OAuthFixture(hass, hass_client_no_auth, aioclient_mock)


class Client:
    """Test client with helper methods for application credentials websocket."""

    def __init__(self, client):
        """Initialize Client."""
        self.client = client
        self.id = 0

    async def cmd(
        self, cmd: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a command and receive the json result."""
        self.id += 1
        await self.client.send_json(
            {
                "id": self.id,
                "type": f"{DOMAIN}/{cmd}",
                **(payload if payload is not None else {}),
            }
        )
        resp = await self.client.receive_json()
        assert resp.get("id") == self.id
        return resp

    async def cmd_result(self, cmd: str, payload: dict[str, Any] | None = None) -> Any:
        """Send a command and parse the result."""
        resp = await self.cmd(cmd, payload)
        assert resp.get("success")
        assert resp.get("type") == "result"
        return resp.get("result")


type ClientFixture = Callable[[], Client]


@pytest.fixture
async def ws_client(hass_ws_client: WebSocketGenerator) -> ClientFixture:
    """Fixture for creating the test websocket client."""

    async def create_client() -> Client:
        ws_client = await hass_ws_client()
        return Client(ws_client)

    return create_client


async def test_websocket_list_empty(ws_client: ClientFixture) -> None:
    """Test websocket list command."""
    client = await ws_client()
    assert await client.cmd_result("list") == []


async def test_websocket_create(ws_client: ClientFixture) -> None:
    """Test websocket create command."""
    client = await ws_client()
    result = await client.cmd_result(
        "create",
        {
            CONF_DOMAIN: TEST_DOMAIN,
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
        },
    )
    assert result == {
        CONF_DOMAIN: TEST_DOMAIN,
        CONF_CLIENT_ID: CLIENT_ID,
        CONF_CLIENT_SECRET: CLIENT_SECRET,
        "id": ID,
    }

    result = await client.cmd_result("list")
    assert result == [
        {
            CONF_DOMAIN: TEST_DOMAIN,
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
            "id": ID,
        }
    ]


async def test_websocket_create_invalid_domain(ws_client: ClientFixture) -> None:
    """Test websocket create command."""
    client = await ws_client()
    resp = await client.cmd(
        "create",
        {
            CONF_DOMAIN: "other-domain",
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
        },
    )
    assert not resp.get("success")
    assert "error" in resp
    assert resp["error"].get("code") == "invalid_format"
    assert (
        resp["error"].get("message")
        == "No application_credentials platform for other-domain"
    )


async def test_websocket_update_not_supported(ws_client: ClientFixture) -> None:
    """Test websocket update command in unsupported."""
    client = await ws_client()
    result = await client.cmd_result(
        "create",
        {
            CONF_DOMAIN: TEST_DOMAIN,
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
        },
    )
    assert result == {
        CONF_DOMAIN: TEST_DOMAIN,
        CONF_CLIENT_ID: CLIENT_ID,
        CONF_CLIENT_SECRET: CLIENT_SECRET,
        "id": ID,
    }

    resp = await client.cmd("update", {"application_credentials_id": ID})
    assert not resp.get("success")
    assert "error" in resp
    assert resp["error"].get("code") == "invalid_format"
    assert resp["error"].get("message") == "Updates not supported"


async def test_websocket_delete(ws_client: ClientFixture) -> None:
    """Test websocket delete command."""
    client = await ws_client()

    await client.cmd_result(
        "create",
        {
            CONF_DOMAIN: TEST_DOMAIN,
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
        },
    )
    assert await client.cmd_result("list") == [
        {
            CONF_DOMAIN: TEST_DOMAIN,
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
            "id": ID,
        }
    ]

    await client.cmd_result("delete", {"application_credentials_id": ID})
    assert await client.cmd_result("list") == []


async def test_websocket_delete_item_not_found(ws_client: ClientFixture) -> None:
    """Test websocket delete command."""
    client = await ws_client()

    resp = await client.cmd("delete", {"application_credentials_id": ID})
    assert not resp.get("success")
    assert "error" in resp
    assert resp["error"].get("code") == "not_found"
    assert (
        resp["error"].get("message")
        == f"Unable to find application_credentials_id {ID}"
    )


@pytest.mark.parametrize("config_credential", [DEVELOPER_CREDENTIAL])
async def test_websocket_import_config(
    ws_client: ClientFixture,
    config_credential: ClientCredential,
    import_config_credential: Any,
) -> None:
    """Test websocket list command for an imported credential."""
    client = await ws_client()

    # Imported creds returned from websocket
    assert await client.cmd_result("list") == [
        {
            CONF_DOMAIN: TEST_DOMAIN,
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
            "id": ID,
            CONF_AUTH_DOMAIN: TEST_DOMAIN,
            CONF_NAME: DEFAULT_IMPORT_NAME,
        }
    ]

    # Imported credential can be deleted
    await client.cmd_result("delete", {"application_credentials_id": ID})
    assert await client.cmd_result("list") == []


@pytest.mark.parametrize("config_credential", [DEVELOPER_CREDENTIAL])
async def test_import_duplicate_credentials(
    hass: HomeAssistant,
    ws_client: ClientFixture,
    config_credential: ClientCredential,
    import_config_credential: Any,
) -> None:
    """Exercise duplicate credentials are ignored."""

    # Import the test credential again and verify it is not imported twice
    await async_import_client_credential(hass, TEST_DOMAIN, DEVELOPER_CREDENTIAL)
    client = await ws_client()
    assert await client.cmd_result("list") == [
        {
            CONF_DOMAIN: TEST_DOMAIN,
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
            "id": ID,
            CONF_AUTH_DOMAIN: TEST_DOMAIN,
            CONF_NAME: DEFAULT_IMPORT_NAME,
        }
    ]


@pytest.mark.parametrize("config_credential", [NAMED_CREDENTIAL])
async def test_import_named_credential(
    ws_client: ClientFixture,
    config_credential: ClientCredential,
    import_config_credential: Any,
) -> None:
    """Test websocket list command for an imported credential."""
    client = await ws_client()

    # Imported creds returned from websocket
    assert await client.cmd_result("list") == [
        {
            CONF_DOMAIN: TEST_DOMAIN,
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
            "id": ID,
            CONF_AUTH_DOMAIN: TEST_DOMAIN,
            CONF_NAME: NAME,
        }
    ]


async def test_config_flow_no_credentials(hass: HomeAssistant) -> None:
    """Test config flow base case with no credentials registered."""
    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "missing_credentials"


async def test_config_flow_other_domain(
    hass: HomeAssistant,
    ws_client: ClientFixture,
    authorization_server: AuthorizationServer,
) -> None:
    """Test config flow ignores credentials for another domain."""
    await setup_application_credentials_integration(
        hass,
        "other_domain",
        authorization_server,
    )
    client = await ws_client()
    await client.cmd_result(
        "create",
        {
            CONF_DOMAIN: "other_domain",
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
        },
    )
    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "missing_credentials"


async def test_config_flow(
    hass: HomeAssistant,
    ws_client: ClientFixture,
    oauth_fixture: OAuthFixture,
) -> None:
    """Test config flow with application credential registered."""
    client = await ws_client()

    await client.cmd_result(
        "create",
        {
            CONF_DOMAIN: TEST_DOMAIN,
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
        },
    )
    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.EXTERNAL_STEP
    result = await oauth_fixture.complete_external_step(result)
    assert (
        result["data"].get("auth_implementation") == "fake_integration_some_client_id"
    )

    # Verify it is not possible to delete an in-use config entry
    resp = await client.cmd("delete", {"application_credentials_id": ID})
    assert not resp.get("success")
    assert "error" in resp
    assert resp["error"].get("code") == "home_assistant_error"
    assert (
        resp["error"].get("message")
        == "Cannot delete credential in use by integration fake_integration"
    )

    # Return information about the in use config entry
    entries = hass.config_entries.async_entries(TEST_DOMAIN)
    assert len(entries) == 1
    client = await ws_client()
    result = await client.cmd_result(
        "config_entry", {"config_entry_id": entries[0].entry_id}
    )
    assert result.get("application_credentials_id") == ID

    # Delete the config entry
    await hass.config_entries.async_remove(entries[0].entry_id)

    # Application credential can now be removed
    resp = await client.cmd("delete", {"application_credentials_id": ID})
    assert resp.get("success")

    # Config entry information no longer found
    result = await client.cmd("config_entry", {"config_entry_id": entries[0].entry_id})
    assert "error" in result
    assert result["error"].get("code") == "invalid_config_entry_id"


async def test_config_flow_multiple_entries(
    hass: HomeAssistant,
    ws_client: ClientFixture,
    oauth_fixture: OAuthFixture,
) -> None:
    """Test config flow with multiple application credentials registered."""
    client = await ws_client()

    await client.cmd_result(
        "create",
        {
            CONF_DOMAIN: TEST_DOMAIN,
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
        },
    )
    await client.cmd_result(
        "create",
        {
            CONF_DOMAIN: TEST_DOMAIN,
            CONF_CLIENT_ID: CLIENT_ID + "2",
            CONF_CLIENT_SECRET: CLIENT_SECRET + "2",
        },
    )
    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "pick_implementation"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"implementation": "fake_integration_some_client_id2"},
    )
    assert result.get("type") is FlowResultType.EXTERNAL_STEP
    oauth_fixture.client_id = CLIENT_ID + "2"
    oauth_fixture.title = CLIENT_ID + "2"
    result = await oauth_fixture.complete_external_step(result)
    assert (
        result["data"].get("auth_implementation") == "fake_integration_some_client_id2"
    )


async def test_config_flow_create_delete_credential(
    hass: HomeAssistant,
    ws_client: ClientFixture,
    oauth_fixture: OAuthFixture,
) -> None:
    """Test adding and deleting a credential unregisters from the config flow."""
    client = await ws_client()

    await client.cmd_result(
        "create",
        {
            CONF_DOMAIN: TEST_DOMAIN,
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
        },
    )
    await client.cmd("delete", {"application_credentials_id": ID})

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "missing_credentials"


@pytest.mark.parametrize("config_credential", [DEVELOPER_CREDENTIAL])
async def test_config_flow_with_config_credential(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    oauth_fixture,
    config_credential,
    import_config_credential,
) -> None:
    """Test config flow with application credential registered."""
    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.EXTERNAL_STEP
    oauth_fixture.title = DEFAULT_IMPORT_NAME
    result = await oauth_fixture.complete_external_step(result)
    # Uses the imported auth domain for compatibility
    assert result["data"].get("auth_implementation") == TEST_DOMAIN


@pytest.mark.parametrize("mock_application_credentials_integration", [None])
async def test_import_without_setup(hass: HomeAssistant, config_credential) -> None:
    """Test import of credentials without setting up the integration."""

    with pytest.raises(ValueError):
        await async_import_client_credential(hass, TEST_DOMAIN, config_credential)

    # Config flow does not have authentication
    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "missing_configuration"


@pytest.mark.parametrize("mock_application_credentials_integration", [None])
async def test_websocket_without_platform(
    hass: HomeAssistant, ws_client: ClientFixture
) -> None:
    """Test an integration without the application credential platform."""
    assert await async_setup_component(hass, "application_credentials", {})
    hass.config.components.add(TEST_DOMAIN)

    client = await ws_client()
    resp = await client.cmd(
        "create",
        {
            CONF_DOMAIN: TEST_DOMAIN,
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
        },
    )
    assert not resp.get("success")
    assert "error" in resp
    assert resp["error"].get("code") == "invalid_format"

    # Config flow does not have authentication
    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "missing_configuration"


@pytest.mark.parametrize("mock_application_credentials_integration", [None])
async def test_websocket_without_authorization_server(
    hass: HomeAssistant, ws_client: ClientFixture
) -> None:
    """Test platform with incorrect implementation."""
    assert await async_setup_component(hass, "application_credentials", {})
    hass.config.components.add(TEST_DOMAIN)

    # Platform does not implemenent async_get_authorization_server
    platform = Mock()
    del platform.async_get_authorization_server
    del platform.async_get_auth_implementation
    mock_platform(
        hass,
        f"{TEST_DOMAIN}.application_credentials",
        platform,
    )

    client = await ws_client()
    resp = await client.cmd(
        "create",
        {
            CONF_DOMAIN: TEST_DOMAIN,
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
        },
    )
    assert not resp.get("success")
    assert "error" in resp
    assert resp["error"].get("code") == "invalid_format"

    # Config flow does not have authentication
    with pytest.raises(ValueError):
        await hass.config_entries.flow.async_init(
            TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
        )


@pytest.mark.parametrize("config_credential", [DEVELOPER_CREDENTIAL])
async def test_platform_with_auth_implementation(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    oauth_fixture,
    config_credential,
    import_config_credential,
    authorization_server,
) -> None:
    """Test config flow with custom OAuth2 implementation."""

    assert await async_setup_component(hass, "application_credentials", {})
    hass.config.components.add(TEST_DOMAIN)

    async def get_auth_impl(
        hass: HomeAssistant, auth_domain: str, credential: ClientCredential
    ) -> config_entry_oauth2_flow.AbstractOAuth2Implementation:
        return AuthImplementation(hass, auth_domain, credential, authorization_server)

    mock_platform_impl = Mock(
        async_get_auth_implementation=get_auth_impl,
    )
    del mock_platform_impl.async_get_authorization_server
    mock_platform(
        hass,
        f"{TEST_DOMAIN}.application_credentials",
        mock_platform_impl,
    )

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.EXTERNAL_STEP
    oauth_fixture.title = DEFAULT_IMPORT_NAME
    result = await oauth_fixture.complete_external_step(result)
    # Uses the imported auth domain for compatibility
    assert result["data"].get("auth_implementation") == TEST_DOMAIN


async def test_websocket_integration_list(ws_client: ClientFixture) -> None:
    """Test websocket integration list command."""
    client = await ws_client()
    with patch(
        "homeassistant.loader.APPLICATION_CREDENTIALS", ["example1", "example2"]
    ):
        assert await client.cmd_result("config") == {
            "domains": ["example1", "example2"],
            "integrations": {
                "example1": {},
                "example2": {},
            },
        }


async def test_name(
    hass: HomeAssistant, ws_client: ClientFixture, oauth_fixture: OAuthFixture
) -> None:
    """Test a credential with a name set."""
    client = await ws_client()
    result = await client.cmd_result(
        "create",
        {
            CONF_DOMAIN: TEST_DOMAIN,
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
            CONF_NAME: NAME,
        },
    )
    assert result == {
        CONF_DOMAIN: TEST_DOMAIN,
        CONF_CLIENT_ID: CLIENT_ID,
        CONF_CLIENT_SECRET: CLIENT_SECRET,
        CONF_NAME: NAME,
        "id": ID,
    }

    result = await client.cmd_result("list")
    assert result == [
        {
            CONF_DOMAIN: TEST_DOMAIN,
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
            CONF_NAME: NAME,
            "id": ID,
        }
    ]

    result = await hass.config_entries.flow.async_init(
        TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.EXTERNAL_STEP
    oauth_fixture.title = NAME
    result = await oauth_fixture.complete_external_step(result)
    assert (
        result["data"].get("auth_implementation") == "fake_integration_some_client_id"
    )


async def test_remove_config_entry_without_app_credentials(
    hass: HomeAssistant,
    ws_client: ClientFixture,
    authorization_server: AuthorizationServer,
) -> None:
    """Test config entry removal for non-app credentials integration."""
    hass.config.components.add("other_domain")
    config_entry = MockConfigEntry(domain="other_domain")
    config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, "other_domain", {})

    entries = hass.config_entries.async_entries("other_domain")
    assert len(entries) == 1

    client = await ws_client()
    result = await client.cmd_result(
        "config_entry", {"config_entry_id": entries[0].entry_id}
    )
    assert "application_credential_id" not in result


async def test_websocket_create_strips_whitespace(ws_client: ClientFixture) -> None:
    """Test websocket create command with whitespace in the credentials."""
    client = await ws_client()
    result = await client.cmd_result(
        "create",
        {
            CONF_DOMAIN: TEST_DOMAIN,
            CONF_CLIENT_ID: f"  {CLIENT_ID}  ",
            CONF_CLIENT_SECRET: f" {CLIENT_SECRET} ",
        },
    )
    assert result == {
        CONF_DOMAIN: TEST_DOMAIN,
        CONF_CLIENT_ID: CLIENT_ID,
        CONF_CLIENT_SECRET: CLIENT_SECRET,
        "id": ID,
    }

    result = await client.cmd_result("list")
    assert result == [
        {
            CONF_DOMAIN: TEST_DOMAIN,
            CONF_CLIENT_ID: CLIENT_ID,
            CONF_CLIENT_SECRET: CLIENT_SECRET,
            "id": ID,
        }
    ]
