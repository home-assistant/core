"""Test the Remember The Milk config flow."""

import asyncio
from collections.abc import Awaitable
from typing import Any
from unittest.mock import AsyncMock, patch

from aiortm import AioRTMError, AuthError
import pytest

from homeassistant import config_entries
from homeassistant.components.remember_the_milk.config_flow import TOKEN_TIMEOUT_SEC
from homeassistant.components.remember_the_milk.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import CREATE_ENTRY_DATA, PROFILE, TOKEN_RESPONSE

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_successful_flow(
    hass: HomeAssistant, client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test successful flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "api_key": "test-api-key",
            "shared_secret": "test-secret",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TOKEN_RESPONSE["user"]["fullname"]
    assert result["data"] == CREATE_ENTRY_DATA
    assert result["result"].unique_id == TOKEN_RESPONSE["user"]["id"]
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (AuthError, "invalid_auth"),
        (AioRTMError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
    client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test form errors when getting the authentication URL."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.remember_the_milk.config_flow.Auth.authenticate_desktop",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "test-api-key",
                "shared_secret": "test-secret",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "api_key": "test-api-key",
            "shared_secret": "test-secret",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TOKEN_RESPONSE["user"]["fullname"]
    assert result["data"] == CREATE_ENTRY_DATA
    assert result["result"].unique_id == TOKEN_RESPONSE["user"]["id"]
    assert len(mock_setup_entry.mock_calls) == 1


async def mock_get_token(*args: Any) -> None:
    """Handle get token."""
    await asyncio.Future()


@pytest.mark.parametrize(
    ("side_effect", "reason", "timeout"),
    [
        (AuthError, "invalid_auth", TOKEN_TIMEOUT_SEC),
        (AioRTMError, "cannot_connect", TOKEN_TIMEOUT_SEC),
        (Exception, "unknown", TOKEN_TIMEOUT_SEC),
        (mock_get_token, "timeout_token", 0),
    ],
)
async def test_token_abort_reasons(
    hass: HomeAssistant,
    client: AsyncMock,
    side_effect: Exception | Awaitable[None],
    reason: str,
    timeout: int,
) -> None:
    """Test abort result when getting token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "api_key": "test-api-key",
            "shared_secret": "test-secret",
        },
    )

    with (
        patch(
            "homeassistant.components.remember_the_milk.config_flow.Auth.get_token",
            side_effect=side_effect,
        ),
        patch(
            "homeassistant.components.remember_the_milk.config_flow.TOKEN_TIMEOUT_SEC",
            timeout,
        ),
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_abort_if_already_configured(
    hass: HomeAssistant, client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Test abort if the same username is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "api_key": "test-api-key",
            "shared_secret": "test-secret",
        },
    )

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow(
    hass: HomeAssistant, client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test import flow with a valid stored token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            "api_key": "test-api-key",
            "shared_secret": "test-secret",
            "name": PROFILE,
            "token": "test-token",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TOKEN_RESPONSE["user"]["fullname"]
    assert result["data"] == {
        "api_key": "test-api-key",
        "shared_secret": "test-secret",
        "token": "test-token",
        "username": PROFILE,
    }
    assert result["result"].unique_id == TOKEN_RESPONSE["user"]["id"]
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("token", "side_effect", "reason"),
    [
        (None, None, "invalid_auth"),
        ("test-token", AuthError, "invalid_auth"),
        ("test-token", AioRTMError, "cannot_connect"),
        ("test-token", Exception, "unknown"),
    ],
)
async def test_import_flow_abort(
    hass: HomeAssistant,
    token: str | None,
    side_effect: type[Exception] | None,
    reason: str,
) -> None:
    """Test import flow aborts without a valid token."""
    with patch(
        "homeassistant.components.remember_the_milk.config_flow.Auth.check_token",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data={
                "api_key": "test-api-key",
                "shared_secret": "test-secret",
                "name": "test-name",
                "token": token,
            },
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


async def test_import_flow_username_mismatch(
    hass: HomeAssistant, client: AsyncMock
) -> None:
    """Test import flow aborts when the token username doesn't match the name."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            "api_key": "test-api-key",
            "shared_secret": "test-secret",
            "name": "other-name",
            "token": "test-token",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "invalid_auth"


async def test_import_flow_already_configured(
    hass: HomeAssistant, client: AsyncMock, config_entry: MockConfigEntry
) -> None:
    """Test import flow aborts when the account name is already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            "api_key": "test-api-key",
            "shared_secret": "test-secret",
            "name": PROFILE,
            "token": "test-token",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
