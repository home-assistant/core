"""Test the homelink config flow."""

from http import HTTPStatus
import time
from unittest.mock import patch

import botocore.exceptions

from homeassistant import config_entries
from homeassistant.components.gentex_homelink.const import DOMAIN, OAUTH2_TOKEN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry
from tests.conftest import AiohttpClientMocker


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM


async def test_full_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Check full flow."""
    with patch(
        "homeassistant.components.gentex_homelink.config_flow.SRPAuth"
    ) as MockSRPAuth:
        instance = MockSRPAuth.return_value
        instance.async_get_access_token.return_value = {
            "AuthenticationResult": {
                "AccessToken": "access",
                "RefreshToken": "refresh",
                "TokenType": "bearer",
                "ExpiresIn": 3600,
            }
        }
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"email": "test@test.com", "password": "SomePassword"},
        )
        aioclient_mock.clear_requests()
        aioclient_mock.post(
            OAUTH2_TOKEN,
            json={
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_at": time.time() + 3600,
                "expires_in": 3600,
            },
        )

        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"]
        assert result["data"]["token"]
        assert result["data"]["token"]["access_token"] == "access"
        assert result["data"]["token"]["refresh_token"] == "refresh"
        assert result["data"]["token"]["expires_in"] == 3600
        assert result["data"]["token"]["expires_at"]


async def test_auth_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test if the auth server returns an error refreshing the token."""
    with patch(
        "homeassistant.components.gentex_homelink.config_flow.SRPAuth"
    ) as MockSRPAuth:
        instance = MockSRPAuth.return_value
        instance.async_get_access_token.return_value = {
            "AuthenticationResult": {
                "AccessToken": "access",
                "RefreshToken": "refresh",
                "TokenType": "bearer",
                "ExpiresIn": 3600,
            }
        }
        aioclient_mock.clear_requests()
        aioclient_mock.post(OAUTH2_TOKEN, status=HTTPStatus.UNAUTHORIZED)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"email": "test@test.com", "password": "SomePassword"},
        )


async def test_reauth_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the reauth flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,
        version=1,
        data={
            "auth_implementation": "gentex_homelink",
            "token": {
                "expires_at": time.time() + 10000,
                "access_token": "",
                "refresh_token": "",
            },
            "last_update_id": None,
        },
        state=config_entries.ConfigEntryState.LOADED,
    )
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: "fake2@email.com", CONF_PASSWORD: "password"},
    )


async def test_reauth_new_email_flow(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test the flow where it isn't a reauth, it's a new sign in."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=None,
        version=1,
        data={
            "auth_implementation": "gentex_homelink",
            "token": {
                "expires_at": time.time() + 10000,
                "access_token": "",
                "refresh_token": "",
                CONF_EMAIL: "fake@email.com",
            },
            "last_update_id": None,
        },
        state=config_entries.ConfigEntryState.LOADED,
    )
    config_entry.add_to_hass(hass)
    result = await config_entry.start_reauth_flow(hass)
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_EMAIL: "fake2@email.com", CONF_PASSWORD: "password"},
    )


async def test_boto_error(hass: HomeAssistant) -> None:
    """Test exceptions from boto are handled correctly."""
    with patch(
        "homeassistant.components.gentex_homelink.config_flow.SRPAuth"
    ) as MockSRPAuth:
        instance = MockSRPAuth.return_value
        instance.async_get_access_token.side_effect = botocore.exceptions.ClientError(
            {"Error": {}}, "Some operation"
        )

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"email": "test@test.com", "password": "SomePassword"},
        )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 0


async def test_generic_error(hass: HomeAssistant) -> None:
    """Test exceptions from boto are handled correctly."""
    with patch(
        "homeassistant.components.gentex_homelink.config_flow.SRPAuth"
    ) as MockSRPAuth:
        instance = MockSRPAuth.return_value
        instance.async_get_access_token.side_effect = Exception("Some error")

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"email": "test@test.com", "password": "SomePassword"},
        )

    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
