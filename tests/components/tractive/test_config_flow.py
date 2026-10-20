"""Test the tractive config flow."""

from collections.abc import Generator
from contextlib import contextmanager
from http import HTTPStatus
from unittest.mock import patch

import aiohttp
import aiotractive
import pytest
from pytest_homeassistant.common import MockConfigEntry, get_schema_suggested_value

from homeassistant import config_entries
from homeassistant.components.tractive.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

USER_INPUT = {
    "email": "test-email@example.com",
    "password": "test-password",
}
NEW_USER_INPUT = {
    "email": "test-email@example.com",
    "password": "new-password",
}
OTHER_USER_INPUT = {
    "email": "other-email@example.com",
    "password": "other-password",
}


@contextmanager
def _patch_success(user_id: str = "user_id") -> Generator[None]:
    """Patch a successful login without setting up the entry."""
    with (
        patch("aiotractive.api.API.user_id", return_value=user_id),
        patch(
            "homeassistant.components.tractive.async_setup_entry",
            return_value=True,
        ),
    ):
        yield


def _rate_limit_error() -> aiotractive.exceptions.TractiveError:
    """Return a Tractive error caused by an HTTP 429 response."""
    error = aiotractive.exceptions.TractiveError()
    error.__cause__ = aiohttp.ClientResponseError(
        None, (), status=HTTPStatus.TOO_MANY_REQUESTS
    )
    return error


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch("aiotractive.api.API.user_id", return_value="user_id"),
        patch(
            "homeassistant.components.tractive.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "test-email@example.com"
    assert result2["data"] == USER_INPUT
    assert result2["result"].unique_id == "user_id"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aiotractive.api.API.user_id",
        side_effect=aiotractive.exceptions.UnauthorizedError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}

    with _patch_success():
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()
    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aiotractive.api.API.user_id",
        side_effect=aiotractive.exceptions.TractiveError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}

    with _patch_success():
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()
    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_form_rate_limit_exceeded(hass: HomeAssistant) -> None:
    """Test we handle rate limit error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    cause = aiohttp.ClientResponseError(
        None,
        (),
        status=HTTPStatus.TOO_MANY_REQUESTS,
    )
    error = aiotractive.exceptions.TractiveError()
    error.__cause__ = cause

    with patch(
        "aiotractive.api.API.user_id",
        side_effect=error,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "rate_limit_exceeded"}

    with _patch_success():
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()
    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "aiotractive.api.API.user_id",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}

    with _patch_success():
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()
    assert result3["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_entry_already_exists(hass: HomeAssistant) -> None:
    """Test user input for config_entry that already exists."""
    first_entry = MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT,
        unique_id="USERID",
    )
    first_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("aiotractive.api.API.user_id", return_value="USERID"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("source", "step_id", "reason"),
    [
        (config_entries.SOURCE_REAUTH, "reauth_confirm", "reauth_successful"),
        (config_entries.SOURCE_RECONFIGURE, "reconfigure", "reconfigure_successful"),
    ],
)
async def test_update_credentials(
    hass: HomeAssistant, source: str, step_id: str, reason: str
) -> None:
    """Test updating credentials through reauth and reconfigure."""
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT, unique_id="USERID")
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source, "entry_id": entry.entry_id}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == step_id
    assert result["errors"] == {}
    assert (
        get_schema_suggested_value(result["data_schema"].schema, "email")
        == USER_INPUT["email"]
    )

    with (
        patch("aiotractive.api.API.user_id", return_value="USERID"),
        patch(
            "homeassistant.components.tractive.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            NEW_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == reason
    assert entry.data == NEW_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("source", "step_id", "reason"),
    [
        (config_entries.SOURCE_REAUTH, "reauth_confirm", "reauth_successful"),
        (config_entries.SOURCE_RECONFIGURE, "reconfigure", "reconfigure_successful"),
    ],
)
@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (aiotractive.exceptions.UnauthorizedError(), "invalid_auth"),
        (aiotractive.exceptions.TractiveError(), "cannot_connect"),
        (_rate_limit_error(), "rate_limit_exceeded"),
        (Exception(), "unknown"),
    ],
)
async def test_update_credentials_errors(
    hass: HomeAssistant,
    source: str,
    step_id: str,
    reason: str,
    side_effect: Exception,
    error: str,
) -> None:
    """Test errors while updating credentials and recovery."""
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT, unique_id="USERID")
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source, "entry_id": entry.entry_id}
    )

    with patch("aiotractive.api.API.user_id", side_effect=side_effect):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            NEW_USER_INPUT,
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == step_id
    assert result2["errors"] == {"base": error}

    with _patch_success("USERID"):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            NEW_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == reason
    assert entry.data == NEW_USER_INPUT


@pytest.mark.parametrize(
    "source", [config_entries.SOURCE_REAUTH, config_entries.SOURCE_RECONFIGURE]
)
async def test_update_credentials_unique_id_mismatch(
    hass: HomeAssistant, source: str
) -> None:
    """Test updating credentials with credentials of a different account."""
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT, unique_id="USERID")
    entry.add_to_hass(hass)
    other_entry = MockConfigEntry(
        domain=DOMAIN,
        data=OTHER_USER_INPUT,
        unique_id="USERID_DIFFERENT",
    )
    other_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": source, "entry_id": entry.entry_id}
    )

    with (
        patch("aiotractive.api.API.user_id", return_value="USERID_DIFFERENT"),
        patch(
            "homeassistant.components.tractive.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            OTHER_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "unique_id_mismatch"
    assert entry.data == USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 0
