"""Test the Remember The Milk config flow."""

import asyncio
from collections.abc import Awaitable
from copy import deepcopy
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.remember_the_milk.config_flow import (
    TOKEN_TIMEOUT_SEC,
    AuthError,
    ResponseError,
)
from homeassistant.components.remember_the_milk.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import CREATE_ENTRY_DATA, PROFILE

from tests.common import MockConfigEntry

TOKEN_DATA = {
    "token": "test-token",
    "user": {
        "fullname": PROFILE,
        "id": "test-user-id",
        "username": PROFILE,
    },
}

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_successful_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test successful flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.remember_the_milk.config_flow.Auth.authenticate_desktop",
        return_value=("https://test-url.com", "test-frob"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "test-api-key",
                "shared_secret": "test-secret",
            },
        )

    with patch(
        "homeassistant.components.remember_the_milk.config_flow.Auth.get_token",
        return_value=TOKEN_DATA,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == PROFILE
    assert result["data"] == CREATE_ENTRY_DATA
    assert result["result"].unique_id == "test-user-id"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (AuthError, "invalid_auth"),
        (ResponseError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_errors(
    hass: HomeAssistant,
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
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "test-api-key",
                "shared_secret": "test-secret",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": error}

    with patch(
        "homeassistant.components.remember_the_milk.config_flow.Auth.authenticate_desktop",
        return_value=("https://test-url.com", "test-frob"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "test-api-key",
                "shared_secret": "test-secret",
            },
        )

    with patch(
        "homeassistant.components.remember_the_milk.config_flow.Auth.get_token",
        return_value=TOKEN_DATA,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == PROFILE
    assert result["data"] == CREATE_ENTRY_DATA
    assert result["result"].unique_id == "test-user-id"
    assert len(mock_setup_entry.mock_calls) == 1


async def mock_get_token(*args: Any) -> None:
    """Handle get token."""
    await asyncio.Future()


@pytest.mark.parametrize(
    ("side_effect", "reason", "timeout"),
    [
        (AuthError, "invalid_auth", TOKEN_TIMEOUT_SEC),
        (ResponseError, "cannot_connect", TOKEN_TIMEOUT_SEC),
        (Exception, "unknown", TOKEN_TIMEOUT_SEC),
        (mock_get_token, "timeout_token", 0),
    ],
)
async def test_token_abort_reasons(
    hass: HomeAssistant,
    side_effect: Exception | Awaitable[None],
    reason: str,
    timeout: int,
) -> None:
    """Test abort result when getting token."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.remember_the_milk.config_flow.Auth.authenticate_desktop",
        return_value=("https://test-url.com", "test-frob"),
    ):
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

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == reason


async def test_abort_if_already_configured(hass: HomeAssistant) -> None:
    """Test abort if the same username is already configured."""
    mock_entry = MockConfigEntry(domain=DOMAIN, unique_id="test-user-id")
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert not result["errors"]

    with patch(
        "homeassistant.components.remember_the_milk.config_flow.Auth.authenticate_desktop",
        return_value=("https://test-url.com", "test-frob"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "test-api-key",
                "shared_secret": "test-secret",
            },
        )

    with patch(
        "homeassistant.components.remember_the_milk.config_flow.Auth.get_token",
        return_value=TOKEN_DATA,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    "source", [config_entries.SOURCE_IMPORT, config_entries.SOURCE_USER]
)
@pytest.mark.parametrize(
    ("reauth_unique_id", "abort_reason", "abort_entry_data"),
    [
        (
            "test-user-id",
            "reauth_successful",
            CREATE_ENTRY_DATA | {"token": "new-test-token"},
        ),
        ("other-user-id", "unique_id_mismatch", CREATE_ENTRY_DATA),
    ],
)
async def test_reauth(
    hass: HomeAssistant,
    source: str,
    reauth_unique_id: str,
    abort_reason: str,
    abort_entry_data: dict[str, str],
) -> None:
    """Test reauth flow."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN, unique_id="test-user-id", data=CREATE_ENTRY_DATA, source=source
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reauth_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.remember_the_milk.config_flow.Auth.authenticate_desktop",
        return_value=("https://test-url.com", "test-frob"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "test-api-key",
                "shared_secret": "test-secret",
            },
        )
    reauth_data: dict[str, Any] = deepcopy(TOKEN_DATA) | {"token": "new-test-token"}
    reauth_data["user"]["id"] = reauth_unique_id
    with patch(
        "homeassistant.components.remember_the_milk.config_flow.Auth.get_token",
        return_value=reauth_data,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == abort_reason
    assert mock_entry.data == abort_entry_data
    assert mock_entry.unique_id == "test-user-id"


async def test_import_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test import flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={
            "api_key": "test-api-key",
            "shared_secret": "test-secret",
            "name": "test-name",
        },
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-name"
    assert result["data"] == {
        "api_key": "test-api-key",
        "shared_secret": "test-secret",
        "token": None,
        "username": "test-name",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_reauth_imported_entry(hass: HomeAssistant) -> None:
    """Test reauth flow for an imported entry."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "test-api-key",
            "shared_secret": "test-secret",
            "token": None,
            "username": "test-name",
        },
        source=config_entries.SOURCE_IMPORT,
    )
    mock_entry.add_to_hass(hass)

    result = await mock_entry.start_reauth_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.remember_the_milk.config_flow.Auth.authenticate_desktop",
        return_value=("https://test-url.com", "test-frob"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "test-api-key",
                "shared_secret": "test-secret",
            },
        )

    with patch(
        "homeassistant.components.remember_the_milk.config_flow.Auth.get_token",
        return_value=TOKEN_DATA,
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_entry.data == CREATE_ENTRY_DATA
    assert mock_entry.unique_id == "test-user-id"
