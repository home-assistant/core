"""Test the Twitch config flow."""

import time
from unittest.mock import patch

import pytest
from twitchAPI.twitch import TwitchAPIException, TwitchAuthorizationException

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.application_credentials import (
    ClientCredential,
    async_import_client_credential,
)
from homeassistant.components.twitch.const import (
    CONF_CHANNELS,
    DOMAIN,
    OAUTH2_AUTHORIZE,
    OAUTH2_TOKEN,
    OAUTH_SCOPES,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.setup import async_setup_component

from . import (
    CHANNELS,
    CLIENT_ID,
    CLIENT_SECRET,
    TWITCH_FOLLOWER,
    TWITCH_USER,
    create_response,
)

from tests.common import MockConfigEntry


@pytest.fixture
async def setup_credentials(hass: HomeAssistant) -> None:
    """Fixture to setup credentials."""
    assert await async_setup_component(hass, "application_credentials", {})
    await async_import_client_credential(
        hass,
        DOMAIN,
        ClientCredential(CLIENT_ID, CLIENT_SECRET),
    )


async def _setup_test(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
) -> data_entry_flow.FlowResult:
    """Set up test with oauth credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    state = config_entry_oauth2_flow._encode_jwt(  # pylint: disable=protected-access
        hass,
        {
            "flow_id": result["flow_id"],
            "redirect_uri": "https://example.com/auth/external/callback",
        },
    )

    assert result["url"] == (
        f"{OAUTH2_AUTHORIZE}?response_type=code&client_id={CLIENT_ID}"
        "&redirect_uri=https://example.com/auth/external/callback"
        f"&state={state}"
        f"&scope={','.join([scope.value for scope in OAUTH_SCOPES])}"
    )

    client = await hass_client_no_auth()
    resp = await client.get(f"/auth/external/callback?code=abcd&state={state}")
    assert resp.status == 200
    assert resp.headers["content-type"] == "text/html; charset=utf-8"

    aioclient_mock.post(
        OAUTH2_TOKEN,
        json={
            "refresh_token": "mock-refresh-token",
            "access_token": "mock-access-token",
            "type": "Bearer",
            "expires_in": 60,
        },
    )

    return result


async def _setup_test_good(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
) -> data_entry_flow.FlowResult:
    """Set up test with with good initial config."""
    result = await _setup_test(hass, hass_client_no_auth, aioclient_mock)

    with patch(
        "homeassistant.components.twitch.config_flow.Twitch.set_user_authentication"
    ), patch(
        "homeassistant.components.twitch.config_flow.Twitch.get_users",
        return_value=create_response([TWITCH_USER]),
    ), patch(
        "homeassistant.components.twitch.config_flow.Twitch.get_users_follows",
        return_value=create_response([TWITCH_FOLLOWER]),
    ), patch(
        "homeassistant.components.twitch.async_setup_entry", return_value=True
    ):
        return await hass.config_entries.flow.async_configure(result["flow_id"])


async def _setup_mock_config_entry(
    hass: HomeAssistant,
) -> MockConfigEntry:
    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "auth_implementation": DOMAIN,
            "token": {
                "refresh_token": "mock-refresh-token",
                "access_token": "mock-access-token",
                "type": "Bearer",
                "expires_in": 60,
                "expires_at": time.time() + 60,
            },
            "user": TWITCH_USER,
        },
        options={
            CONF_CHANNELS: [*CHANNELS, "789"],
        },
    )
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


async def test_full_flow(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,  # pylint: disable=redefined-outer-name
) -> None:
    """Check full flow."""
    result = await _setup_test_good(hass, hass_client_no_auth, aioclient_mock)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.twitch.config_flow.Twitch.get_users",
        return_value=create_response([TWITCH_USER]),
    ), patch(
        "homeassistant.components.twitch.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_CHANNELS: CHANNELS,
            },
        )

    assert result2["data"]["user"] == TWITCH_USER
    assert result2["title"] == "Test"
    assert result2["options"] == {CONF_CHANNELS: CHANNELS}
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_pagination(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,  # pylint: disable=redefined-outer-name
) -> None:
    """Check paginated follower response."""
    result = await _setup_test(hass, hass_client_no_auth, aioclient_mock)

    followers = create_response([TWITCH_FOLLOWER])

    with patch(
        "homeassistant.components.twitch.config_flow.Twitch.set_user_authentication"
    ), patch(
        "homeassistant.components.twitch.config_flow.Twitch.get_users",
        return_value=create_response([TWITCH_USER]),
    ), patch(
        "homeassistant.components.twitch.config_flow.Twitch.get_users_follows",
        side_effect=[
            {
                **followers,
                "pagination": {"cursor": 3},
            },
            followers,
        ],
    ), patch(
        "homeassistant.components.twitch.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] is None


async def test_bad_user(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,  # pylint: disable=redefined-outer-name
) -> None:
    """Check missing user from response."""
    result = await _setup_test(hass, hass_client_no_auth, aioclient_mock)

    with patch(
        "homeassistant.components.twitch.config_flow.Twitch.set_user_authentication"
    ), patch(
        "homeassistant.components.twitch.config_flow.Twitch.get_users",
        return_value={},
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "user_not_found"


async def test_authorization_error(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,  # pylint: disable=redefined-outer-name
) -> None:
    """Test authorization error when getting users."""
    result = await _setup_test(hass, hass_client_no_auth, aioclient_mock)

    with patch(
        "homeassistant.components.twitch.config_flow.Twitch.set_user_authentication"
    ), patch(
        "homeassistant.components.twitch.config_flow.Twitch.get_users",
        side_effect=TwitchAuthorizationException,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "invalid_auth"


async def test_api_error(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,  # pylint: disable=redefined-outer-name
) -> None:
    """Test api error when getting users."""
    result = await _setup_test(hass, hass_client_no_auth, aioclient_mock)

    with patch(
        "homeassistant.components.twitch.config_flow.Twitch.set_user_authentication"
    ), patch(
        "homeassistant.components.twitch.config_flow.Twitch.get_users",
        side_effect=TwitchAPIException,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_followers_api_error(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,  # pylint: disable=redefined-outer-name
) -> None:
    """Test api error when getting followers."""
    result = await _setup_test(hass, hass_client_no_auth, aioclient_mock)

    with patch(
        "homeassistant.components.twitch.config_flow.Twitch.set_user_authentication"
    ), patch(
        "homeassistant.components.twitch.config_flow.Twitch.get_users",
        return_value=create_response([TWITCH_USER]),
    ), patch(
        "homeassistant.components.twitch.config_flow.Twitch.get_users_follows",
        side_effect=TwitchAPIException,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_already_configured(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,  # pylint: disable=redefined-outer-name
) -> None:
    """Test we abort if already configured."""
    mock_config_entry = MockConfigEntry(domain=DOMAIN)
    mock_config_entry.add_to_hass(hass)

    result = await _setup_test_good(hass, hass_client_no_auth, aioclient_mock)

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_options_flow(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,  # pylint: disable=redefined-outer-name
) -> None:
    """Test options flow."""
    mock_config_entry = await _setup_mock_config_entry(hass)

    with patch(
        "homeassistant.components.twitch.config_flow.Twitch.set_user_authentication"
    ), patch(
        "homeassistant.components.twitch.config_flow.Twitch.get_users",
        return_value=create_response([TWITCH_USER]),
    ), patch(
        "homeassistant.components.twitch.config_flow.Twitch.get_users_follows",
        return_value=create_response([TWITCH_FOLLOWER]),
    ):
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

    assert result["type"] == "form"
    assert result["step_id"] == "channels"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_CHANNELS: ["123"],
        },
    )

    assert "123" in result["data"][CONF_CHANNELS]
    assert "456" not in result["data"][CONF_CHANNELS]


async def test_options_authorization_error(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,  # pylint: disable=redefined-outer-name
) -> None:
    """Test authorization error when getting users in options flow."""
    mock_config_entry = await _setup_mock_config_entry(hass)

    with patch(
        "homeassistant.components.twitch.config_flow.Twitch.set_user_authentication"
    ), patch(
        "homeassistant.components.twitch.config_flow.Twitch.get_users_follows",
        side_effect=TwitchAuthorizationException,
    ):
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "invalid_auth"


async def test_options_api_error(
    hass: HomeAssistant,
    hass_client_no_auth,
    aioclient_mock,
    current_request_with_host,
    setup_credentials,  # pylint: disable=redefined-outer-name
) -> None:
    """Test api error when getting users in options flow."""
    mock_config_entry = await _setup_mock_config_entry(hass)

    with patch(
        "homeassistant.components.twitch.config_flow.Twitch.set_user_authentication"
    ), patch(
        "homeassistant.components.twitch.config_flow.Twitch.get_users_follows",
        side_effect=TwitchAPIException,
    ):
        result = await hass.config_entries.options.async_init(
            mock_config_entry.entry_id
        )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
