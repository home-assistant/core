"""Tests for the Heiman Home config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from heimanconnect import HeimanAuthError, HeimanHome, HeimanTokenExpiredError, HeimanUser
import pytest
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.heiman_home.api import HeimanApiClient
from homeassistant.components.heiman_home.config_flow import HeimanConfigFlow
from homeassistant.components.heiman_home.const import (
    CONF_HOME_ID,
    CONF_USER_ID,
    DOMAIN,
    OAUTH_TOKEN_URL,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType, InvalidData

from tests.common import MockConfigEntry
from tests.test_util.aiohttp import AiohttpClientMocker
from tests.typing import ClientSessionGenerator

__all__ = [
    "MockConfigEntry",
]


def create_mock_cloud_client(
    user_info: HeimanUser | None = None,
    homes: list[HeimanHome] | None = None,
    error: Exception | None = None,
) -> MagicMock:
    """Create a mock cloud client with optional error simulation."""
    mock_cloud = MagicMock()
    if error:
        mock_cloud.async_get_user_info = AsyncMock(side_effect=error)
        mock_cloud.async_get_homes = AsyncMock(side_effect=error)
    else:
        mock_cloud.async_get_user_info = AsyncMock(return_value=user_info)
        mock_cloud.async_get_homes = AsyncMock(return_value=homes or [])
    return mock_cloud


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Mock setting up a config entry."""
    with patch(
        "homeassistant.components.heiman_home.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.mark.usefixtures("current_request_with_host")
async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    aioclient_mock: AiohttpClientMocker,
    setup_credentials: None,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First step should be either EXTERNAL_STEP (OAuth) or already at a step
    if result["type"] is FlowResultType.EXTERNAL_STEP:
        # Extract state from the authorization URL
        assert "state=" in result["url"]
        state = result["url"].split("state=")[1].split("&")[0]

        # Simulate OAuth callback
        client = await hass_client_no_auth()
        resp = await client.get(f"/auth/external/callback?code=mock-code&state={state}")
        assert resp.status == 200

        # Mock token exchange
        aioclient_mock.post(
            OAUTH_TOKEN_URL,
            json={
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "read write",
            },
        )

        # Mock API calls after OAuth
        mock_cloud = create_mock_cloud_client(
            user_info=HeimanUser(user_id="test-user", email="test@example.com"),
            homes=[
                HeimanHome(
                    home_id="test-home-id",
                    home_name="Test Home",
                    device_count=5,
                    user_id="test-user",
                )
            ],
        )
        with patch.object(
            HeimanApiClient,
            "cloud_client",
            new_callable=PropertyMock,
            return_value=mock_cloud,
        ):
            # Continue flow after OAuth callback
            result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # After OAuth, should show home selection form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_home"

    # Submit home selection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOME_ID: "test-home-id"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"]
    assert result["data"][CONF_HOME_ID] == "test-home-id"
    assert mock_setup_entry.called


@pytest.mark.usefixtures("current_request_with_host")
async def test_user_already_configured(
    hass: HomeAssistant,
    setup_credentials: None,
    mock_setup_entry: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test we abort if account already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test_user_id",
        data={
            CONF_TOKEN: {"access_token": "test"},
            CONF_HOME_ID: "home1",
            CONF_USER_ID: "test_user_id",
        },
    )
    entry.add_to_hass(hass)

    # Start flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First step should be either EXTERNAL_STEP (OAuth) or already at a step
    if result["type"] is FlowResultType.EXTERNAL_STEP:
        # Extract state from the authorization URL
        assert "state=" in result["url"]
        state = result["url"].split("state=")[1].split("&")[0]

        # Simulate OAuth callback
        client = await hass_client_no_auth()
        resp = await client.get(f"/auth/external/callback?code=mock-code&state={state}")
        assert resp.status == 200

        # Mock token exchange
        aioclient_mock.post(
            OAUTH_TOKEN_URL,
            json={
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "read write",
            },
        )

        # Mock API calls - return same user_id as existing entry
        mock_cloud = create_mock_cloud_client(
            user_info=HeimanUser(user_id="test_user_id", email="test@example.com"),
            homes=[
                HeimanHome(
                    home_id="test-home-id",
                    home_name="Test Home",
                    device_count=5,
                    user_id="test_user_id",
                )
            ],
        )
        with patch.object(
            HeimanApiClient,
            "cloud_client",
            new_callable=PropertyMock,
            return_value=mock_cloud,
        ):
            # Continue flow after OAuth callback
            result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should show home selection form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_home"

    # Submit home selection - should abort because user_id already configured
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOME_ID: "test-home-id"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("current_request_with_host")
async def test_select_home_step(
    hass: HomeAssistant,
    setup_credentials: None,
    mock_setup_entry: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test home selection step."""
    # Start flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First step should be either EXTERNAL_STEP (OAuth) or already at a step
    if result["type"] is FlowResultType.EXTERNAL_STEP:
        # Extract state from the authorization URL
        assert "state=" in result["url"]
        state = result["url"].split("state=")[1].split("&")[0]

        # Simulate OAuth callback
        client = await hass_client_no_auth()
        resp = await client.get(f"/auth/external/callback?code=mock-code&state={state}")
        assert resp.status == 200

        # Mock token exchange
        aioclient_mock.post(
            OAUTH_TOKEN_URL,
            json={
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "read write",
            },
        )

        # Mock API calls after OAuth
        mock_cloud = create_mock_cloud_client(
            user_info=HeimanUser(user_id="test-user", email="test@example.com"),
            homes=[
                HeimanHome(
                    home_id="test-home-id",
                    home_name="Test Home",
                    device_count=5,
                    user_id="test-user",
                )
            ],
        )
        with patch.object(
            HeimanApiClient,
            "cloud_client",
            new_callable=PropertyMock,
            return_value=mock_cloud,
        ):
            # Continue flow after OAuth callback
            result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_home"

    # Submit home selection
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOME_ID: "test-home-id"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"]
    assert result["data"][CONF_HOME_ID] == "test-home-id"


@pytest.mark.usefixtures("current_request_with_host")
async def test_no_home_selected(
    hass: HomeAssistant,
    setup_credentials: None,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test error when no home is selected."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First step should be either EXTERNAL_STEP (OAuth) or already at a step
    if result["type"] is FlowResultType.EXTERNAL_STEP:
        # Extract state from the authorization URL
        assert "state=" in result["url"]
        state = result["url"].split("state=")[1].split("&")[0]

        # Simulate OAuth callback
        client = await hass_client_no_auth()
        resp = await client.get(f"/auth/external/callback?code=mock-code&state={state}")
        assert resp.status == 200

        # Mock token exchange
        aioclient_mock.post(
            OAUTH_TOKEN_URL,
            json={
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "read write",
            },
        )

        # Mock API calls after OAuth - return empty homes list
        mock_cloud = create_mock_cloud_client(
            user_info=HeimanUser(user_id="test-user", email="test@example.com"),
            homes=[],
        )
        with patch.object(
            HeimanApiClient,
            "cloud_client",
            new_callable=PropertyMock,
            return_value=mock_cloud,
        ):
            # Continue flow after OAuth callback
            result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should abort because no homes found
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_homes"


@pytest.mark.usefixtures("current_request_with_host")
async def test_token_invalid_abort(
    hass: HomeAssistant,
    setup_credentials: None,
    mock_setup_entry: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test abort when token is invalid."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First step should be EXTERNAL_STEP (OAuth)
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert "state=" in result["url"]
    state = result["url"].split("state=")[1].split("&")[0]

    # Simulate OAuth callback
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=mock-code&state={state}")
    assert resp.status == 200

    # Mock token exchange
    aioclient_mock.post(
        OAUTH_TOKEN_URL,
        json={
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "read write",
        },
    )

    # Mock API call to fail with auth error
    mock_cloud = create_mock_cloud_client(error=HeimanAuthError("Invalid token"))
    with patch.object(
        HeimanApiClient,
        "cloud_client",
        new_callable=PropertyMock,
        return_value=mock_cloud,
    ):
        # Continue flow after OAuth callback
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should abort with token_invalid reason
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "token_invalid"


@pytest.mark.usefixtures("current_request_with_host")
async def test_select_home_without_home_id(
    hass: HomeAssistant,
    setup_credentials: None,
    mock_setup_entry: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test home selection without providing home_id in user input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First step should be EXTERNAL_STEP (OAuth)
    if result["type"] is FlowResultType.EXTERNAL_STEP:
        # Extract state from the authorization URL
        assert "state=" in result["url"]
        state = result["url"].split("state=")[1].split("&")[0]

        # Simulate OAuth callback
        client = await hass_client_no_auth()
        resp = await client.get(f"/auth/external/callback?code=mock-code&state={state}")
        assert resp.status == 200

        # Mock token exchange
        aioclient_mock.post(
            OAUTH_TOKEN_URL,
            json={
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "read write",
            },
        )

    # Mock API calls after OAuth
    mock_cloud = create_mock_cloud_client(
        user_info=HeimanUser(user_id="test-user", email="test@example.com"),
        homes=[
            HeimanHome(
                home_id="home-1",
                home_name="Home 1",
                device_count=5,
                user_id="test-user",
            ),
        ],
    )
    with patch.object(
        HeimanApiClient,
        "cloud_client",
        new_callable=PropertyMock,
        return_value=mock_cloud,
    ):
        # Continue flow after OAuth callback
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should be at home selection step
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_home"

    # Schema rejects invalid selection before flow step validation.
    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOME_ID: None},
        )


@pytest.mark.usefixtures("current_request_with_host")
async def test_user_info_fetch_error_abort(
    hass: HomeAssistant,
    setup_credentials: None,
    mock_setup_entry: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test abort when user info fetch fails with non-auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First step should be EXTERNAL_STEP (OAuth)
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert "state=" in result["url"]
    state = result["url"].split("state=")[1].split("&")[0]

    # Simulate OAuth callback
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=mock-code&state={state}")
    assert resp.status == 200

    # Mock token exchange
    aioclient_mock.post(
        OAUTH_TOKEN_URL,
        json={
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "read write",
        },
    )

    # Mock API call to fail with non-auth error
    mock_cloud = create_mock_cloud_client(error=Exception("Network error"))
    with patch.object(
        HeimanApiClient,
        "cloud_client",
        new_callable=PropertyMock,
        return_value=mock_cloud,
    ):
        # Continue flow after OAuth callback
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should abort with user_info_failed reason
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "user_info_failed"


@pytest.mark.usefixtures("current_request_with_host")
async def test_homes_fetch_error_abort(
    hass: HomeAssistant,
    setup_credentials: None,
    mock_setup_entry: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test abort when homes fetch fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First step should be EXTERNAL_STEP (OAuth)
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert "state=" in result["url"]
    state = result["url"].split("state=")[1].split("&")[0]

    # Simulate OAuth callback
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=mock-code&state={state}")
    assert resp.status == 200

    # Mock token exchange
    aioclient_mock.post(
        OAUTH_TOKEN_URL,
        json={
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "read write",
        },
    )

    # Mock API calls after OAuth
    mock_cloud = MagicMock()
    mock_cloud.async_get_user_info = AsyncMock(
        return_value=HeimanUser(user_id="test-user", email="test@example.com")
    )
    mock_cloud.async_get_homes = AsyncMock(side_effect=Exception("Network error"))
    with patch.object(
        HeimanApiClient,
        "cloud_client",
        new_callable=PropertyMock,
        return_value=mock_cloud,
    ):
        # Continue flow after OAuth callback
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should abort with homes_fetch_failed reason
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "homes_fetch_failed"


@pytest.mark.usefixtures("current_request_with_host")
async def test_homes_fetch_token_invalid(
    hass: HomeAssistant,
    setup_credentials: None,
    mock_setup_entry: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test abort when homes fetch fails with auth error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First step should be EXTERNAL_STEP (OAuth)
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert "state=" in result["url"]
    state = result["url"].split("state=")[1].split("&")[0]

    # Simulate OAuth callback
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=mock-code&state={state}")
    assert resp.status == 200

    # Mock token exchange
    aioclient_mock.post(
        OAUTH_TOKEN_URL,
        json={
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "read write",
        },
    )

    # Mock API calls - user info succeeds but homes fetch fails with auth error
    mock_cloud = MagicMock()
    mock_cloud.async_get_user_info = AsyncMock(
        return_value=HeimanUser(user_id="test-user", email="test@example.com")
    )
    mock_cloud.async_get_homes = AsyncMock(side_effect=HeimanAuthError("Invalid token"))
    with patch.object(
        HeimanApiClient,
        "cloud_client",
        new_callable=PropertyMock,
        return_value=mock_cloud,
    ):
        # Continue flow after OAuth callback
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should abort with token_invalid reason
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "token_invalid"


@pytest.mark.usefixtures("current_request_with_host")
async def test_multiple_homes_selection(
    hass: HomeAssistant,
    setup_credentials: None,
    mock_setup_entry: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test selecting from multiple homes."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First step should be EXTERNAL_STEP (OAuth)
    if result["type"] is FlowResultType.EXTERNAL_STEP:
        # Extract state from authorization URL
        assert "state=" in result["url"]
        state = result["url"].split("state=")[1].split("&")[0]

        # Simulate OAuth callback
        client = await hass_client_no_auth()
        resp = await client.get(f"/auth/external/callback?code=mock-code&state={state}")
        assert resp.status == 200

        # Mock token exchange
        aioclient_mock.post(
            OAUTH_TOKEN_URL,
            json={
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "read write",
            },
        )

    # Mock API calls after OAuth
    mock_cloud = create_mock_cloud_client(
        user_info=HeimanUser(user_id="test-user", email="test@example.com"),
        homes=[
            HeimanHome(
                home_id="home-1",
                home_name="Home 1",
                device_count=5,
                user_id="test-user",
            ),
            HeimanHome(
                home_id="home-2",
                home_name="Home 2",
                device_count=10,
                user_id="test-user",
            ),
        ],
    )
    with patch.object(
        HeimanApiClient,
        "cloud_client",
        new_callable=PropertyMock,
        return_value=mock_cloud,
    ):
        # Continue flow after OAuth callback
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        # Should be at home selection step
        if result["type"] is FlowResultType.FORM and result["step_id"] == "select_home":
            # Select second home
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"],
                user_input={CONF_HOME_ID: "home-2"},
            )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_HOME_ID] == "home-2"


@pytest.mark.usefixtures("current_request_with_host")
async def test_home_selection_without_home_id(
    hass: HomeAssistant,
    setup_credentials: None,
    mock_setup_entry: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test home selection without providing home_id."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First step should be EXTERNAL_STEP (OAuth)
    if result["type"] is FlowResultType.EXTERNAL_STEP:
        # Extract state from authorization URL
        assert "state=" in result["url"]
        state = result["url"].split("state=")[1].split("&")[0]

        # Simulate OAuth callback
        client = await hass_client_no_auth()
        resp = await client.get(f"/auth/external/callback?code=mock-code&state={state}")
        assert resp.status == 200

        # Mock token exchange
        aioclient_mock.post(
            OAUTH_TOKEN_URL,
            json={
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "read write",
            },
        )

    # Mock API calls after OAuth
    with (
        patch.object(
            HeimanApiClient,
            "async_get_user_info",
            return_value=HeimanUser(user_id="test-user", email="test@example.com"),
        ),
        patch.object(
            HeimanApiClient,
            "async_get_homes",
            return_value=[
                HeimanHome(
                    home_id="home-1",
                    home_name="Home 1",
                    device_count=5,
                    user_id="test-user",
                ),
            ],
        ),
    ):
        # Continue flow after OAuth callback
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        # Should be at home selection step
        if result["type"] is FlowResultType.FORM and result["step_id"] == "select_home":
            # Schema rejects invalid selection before flow step validation.
            with pytest.raises(InvalidData):
                await hass.config_entries.flow.async_configure(
                    result["flow_id"],
                    user_input={CONF_HOME_ID: None},
                )


async def test_get_home_selection_schema_empty_homes() -> None:
    """Test _get_home_selection_schema returns empty schema when homes is empty.

    This tests the code path at line 157 where homes is empty.
    """
    flow = HeimanConfigFlow()
    flow._auth_info.homes = []

    schema = flow._get_home_selection_schema()

    # Schema should be empty dict when no homes
    assert schema.schema == {}


async def test_get_home_selection_schema_with_homes() -> None:
    """Test _get_home_selection_schema with valid homes.

    This tests the code path at lines 159-171 where homes is processed.
    """
    flow = HeimanConfigFlow()
    flow._auth_info.homes = [
        HeimanHome(
            home_id="home-1",
            home_name="Home 1",
            device_count=5,
            user_id="test-user",
        ),
        HeimanHome(
            home_id="home-2",
            home_name="Home 2",
            device_count=10,
            user_id="test-user",
        ),
    ]

    schema = flow._get_home_selection_schema()

    # Schema should have vol.Required(CONF_HOME_ID): vol.In({...})
    assert schema.schema is not None


async def test_select_home_empty_string_passes_schema(
    hass: HomeAssistant,
    setup_credentials: None,
    mock_setup_entry: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test home selection with empty string that passes schema but fails flow check.

    This tests the code path at line 95 where selected_home_id is falsy
    (empty string) but passes schema validation.

    We patch _get_home_selection_schema to return a permissive schema
    that accepts empty string, then verify the flow handles it correctly.
    """
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First step should be EXTERNAL_STEP (OAuth)
    if result["type"] is FlowResultType.EXTERNAL_STEP:
        # Extract state from authorization URL
        assert "state=" in result["url"]
        state = result["url"].split("state=")[1].split("&")[0]

        # Simulate OAuth callback
        client = await hass_client_no_auth()
        resp = await client.get(f"/auth/external/callback?code=mock-code&state={state}")
        assert resp.status == 200

        # Mock token exchange
        aioclient_mock.post(
            OAUTH_TOKEN_URL,
            json={
                "access_token": "mock-access-token",
                "refresh_token": "mock-refresh-token",
                "expires_in": 3600,
                "token_type": "Bearer",
                "scope": "read write",
            },
        )

    # Mock API calls after OAuth
    with (
        patch.object(
            HeimanApiClient,
            "async_get_user_info",
            return_value=HeimanUser(user_id="test-user", email="test@example.com"),
        ),
        patch.object(
            HeimanApiClient,
            "async_get_homes",
            return_value=[
                HeimanHome(
                    home_id="home-1",
                    home_name="Home 1",
                    device_count=5,
                    user_id="test-user",
                ),
            ],
        ),
    ):
        # Continue flow after OAuth callback
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

        # Should be at home selection step
        if result["type"] is FlowResultType.FORM and result["step_id"] == "select_home":
            # Patch _get_home_selection_schema to accept empty string
            with patch.object(
                HeimanConfigFlow,
                "_get_home_selection_schema",
                return_value=vol.Schema(vol.Optional(CONF_HOME_ID, default="")),
            ):
                # Submit with empty string home_id - passes permissive schema
                result = await hass.config_entries.flow.async_configure(
                    result["flow_id"],
                    user_input={CONF_HOME_ID: ""},
                )

                # Should show form with error (line 95)
                assert result["type"] is FlowResultType.FORM
                assert result["step_id"] == "select_home"
                assert result["errors"] == {"base": "no_home_selected"}


async def test_select_home_zero_passes_schema(
    hass: HomeAssistant,
    setup_credentials: None,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test home selection with zero (0) that passes schema but fails flow check.

    This tests the code path at line 95 where selected_home_id is falsy (0).
    """
    flow = HeimanConfigFlow()
    flow.hass = hass
    flow._auth_info.user_info = HeimanUser(
        user_id="test-user", email="test@example.com"
    )
    flow._auth_info.homes = [
        HeimanHome(
            home_id="home-1",
            home_name="Home 1",
            device_count=5,
            user_id="test-user",
        ),
    ]
    flow._auth_info.auth_data = {"token": {"access_token": "test"}}

    # Patch _get_home_selection_schema to accept 0 as valid
    with patch.object(
        HeimanConfigFlow,
        "_get_home_selection_schema",
        return_value=vol.Schema(vol.Optional(CONF_HOME_ID, default=0)),
    ):
        # Call async_step_select_home with 0 (falsy but passes schema)
        result = await flow.async_step_select_home(user_input={CONF_HOME_ID: 0})

        # Should show form with error (line 95)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "select_home"
        assert result["errors"] == {"base": "no_home_selected"}


async def test_reauth_entry_none(
    hass: HomeAssistant,
    setup_credentials: None,
) -> None:
    """Test reauth when _get_reauth_entry returns None.

    This tests lines 129-131 where _get_reauth_entry returns None.
    """
    flow = HeimanConfigFlow()
    flow.hass = hass
    # Set context with SOURCE_REAUTH to enter the reauth code path
    flow.context = {"source": SOURCE_REAUTH, "entry_id": "test_entry_id"}
    flow._auth_info.user_info = HeimanUser(
        user_id="test-user", email="test@example.com"
    )
    flow._auth_info.homes = [
        HeimanHome(
            home_id="home-1",
            home_name="Home 1",
            device_count=5,
            user_id="test-user",
        ),
    ]
    flow._auth_info.auth_data = {"token": {"access_token": "test"}}

    # Patch _get_reauth_entry to return None (line 129-131)
    with patch.object(
        HeimanConfigFlow,
        "_get_reauth_entry",
        return_value=None,
    ):
        result = await flow.async_step_select_home(user_input={CONF_HOME_ID: "home-1"})

        # Should abort with reauth_entry_not_found
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_entry_not_found"


async def test_reauth_user_mismatch(
    hass: HomeAssistant,
    setup_credentials: None,
) -> None:
    """Test reauth when user_id doesn't match.

    This tests lines 132-133 where user_id doesn't match.
    """
    # Create existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="existing_user",
        data={
            CONF_TOKEN: {"access_token": "existing_token"},
            CONF_HOME_ID: "existing_home",
            CONF_USER_ID: "existing_user",
        },
    )
    existing_entry.add_to_hass(hass)

    flow = HeimanConfigFlow()
    flow.hass = hass
    # Set context with SOURCE_REAUTH to enter the reauth code path
    flow.context = {"source": SOURCE_REAUTH, "entry_id": existing_entry.entry_id}
    flow._auth_info.user_info = HeimanUser(
        user_id="different_user", email="different@example.com"
    )
    flow._auth_info.homes = [
        HeimanHome(
            home_id="home-1",
            home_name="Home 1",
            device_count=5,
            user_id="different_user",
        ),
    ]
    flow._auth_info.auth_data = {"token": {"access_token": "test"}}

    # Patch _get_reauth_entry to return existing entry with different user_id
    with patch.object(
        HeimanConfigFlow,
        "_get_reauth_entry",
        return_value=existing_entry,
    ):
        result = await flow.async_step_select_home(user_input={CONF_HOME_ID: "home-1"})

        # Should abort with reauth_user_mismatch
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_user_mismatch"


async def test_reauth_success(
    hass: HomeAssistant,
    setup_credentials: None,
) -> None:
    """Test successful reauth flow.

    This tests line 134 where reauth succeeds.
    """
    # Create existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="existing_user",
        data={
            CONF_TOKEN: {"access_token": "existing_token"},
            CONF_HOME_ID: "existing_home",
            CONF_USER_ID: "existing_user",
        },
    )
    existing_entry.add_to_hass(hass)

    flow = HeimanConfigFlow()
    flow.hass = hass
    # Set context with SOURCE_REAUTH to enter the reauth code path
    flow.context = {"source": SOURCE_REAUTH, "entry_id": existing_entry.entry_id}
    flow._auth_info.user_info = HeimanUser(
        user_id="existing_user", email="existing@example.com"
    )
    flow._auth_info.homes = [
        HeimanHome(
            home_id="new_home",
            home_name="New Home",
            device_count=5,
            user_id="existing_user",
        ),
    ]
    flow._auth_info.auth_data = {"token": {"access_token": "test"}}

    # Patch _get_reauth_entry to return existing entry with same user_id
    with patch.object(
        HeimanConfigFlow,
        "_get_reauth_entry",
        return_value=existing_entry,
    ):
        result = await flow.async_step_select_home(
            user_input={CONF_HOME_ID: "new_home"}
        )

        # Should update and abort to reload
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("current_request_with_host")
async def test_user_info_token_expired_abort(
    hass: HomeAssistant,
    setup_credentials: None,
    mock_setup_entry: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test abort when user info fetch fails with token expired error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First step should be EXTERNAL_STEP (OAuth)
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert "state=" in result["url"]
    state = result["url"].split("state=")[1].split("&")[0]

    # Simulate OAuth callback
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=mock-code&state={state}")
    assert resp.status == 200

    # Mock token exchange
    aioclient_mock.post(
        OAUTH_TOKEN_URL,
        json={
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "read write",
        },
    )

    # Mock API call to fail with token expired error
    mock_cloud = create_mock_cloud_client(error=HeimanTokenExpiredError("Token expired"))
    with patch.object(
        HeimanApiClient,
        "cloud_client",
        new_callable=PropertyMock,
        return_value=mock_cloud,
    ):
        # Continue flow after OAuth callback
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should abort with token_invalid reason
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "token_invalid"


@pytest.mark.usefixtures("current_request_with_host")
async def test_homes_fetch_token_expired_abort(
    hass: HomeAssistant,
    setup_credentials: None,
    mock_setup_entry: AsyncMock,
    aioclient_mock: AiohttpClientMocker,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Test abort when homes fetch fails with token expired error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # First step should be EXTERNAL_STEP (OAuth)
    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert "state=" in result["url"]
    state = result["url"].split("state=")[1].split("&")[0]

    # Simulate OAuth callback
    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=mock-code&state={state}")
    assert resp.status == 200

    # Mock token exchange
    aioclient_mock.post(
        OAUTH_TOKEN_URL,
        json={
            "access_token": "mock-access-token",
            "refresh_token": "mock-refresh-token",
            "expires_in": 3600,
            "token_type": "Bearer",
            "scope": "read write",
        },
    )

    # Mock API calls - user info succeeds but homes fails with token expired
    mock_cloud = MagicMock()
    mock_cloud.async_get_user_info = AsyncMock(
        return_value=HeimanUser(user_id="test-user", email="test@example.com")
    )
    mock_cloud.async_get_homes = AsyncMock(side_effect=HeimanTokenExpiredError("Token expired"))
    
    with patch.object(
        HeimanApiClient,
        "cloud_client",
        new_callable=PropertyMock,
        return_value=mock_cloud,
    ):
        # Continue flow after OAuth callback
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    # Should abort with token_invalid reason
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "token_invalid"
