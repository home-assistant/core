"""Tests for the Schluter DITRA-HEAT config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.schluter.api import (
    CannotConnectError,
    InvalidCredentialsError,
    SchluterApi,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration
from .conftest import DOMAIN

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_flow_api() -> AsyncMock:
    """Patch SchluterApi used inside the config flow."""
    with patch(
        "homeassistant.components.schluter.config_flow.SchluterApi"
    ) as mock_class:
        mock_api = AsyncMock(spec=SchluterApi)
        mock_api.async_get_session.return_value = "test-session-id"
        mock_class.return_value = mock_api
        yield mock_api


async def test_user_flow_success(
    hass: HomeAssistant,
    mock_config_flow_api: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the happy-path user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "user@example.com"
    assert result["data"] == {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: "secret",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (InvalidCredentialsError, "invalid_auth"),
        (CannotConnectError, "cannot_connect"),
        (Exception, "unknown"),
    ],
    ids=["invalid_auth", "cannot_connect", "unknown"],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_config_flow_api: AsyncMock,
    mock_setup_entry: AsyncMock,
    side_effect: type[Exception],
    expected_error: str,
) -> None:
    """Test that errors in the user flow are surfaced correctly."""
    mock_config_flow_api.async_get_session.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "bad"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    assert len(mock_setup_entry.mock_calls) == 0

    # Verify recovery: correct credentials succeed after an error
    mock_config_flow_api.async_get_session.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_already_configured(
    hass: HomeAssistant,
    mock_config_flow_api: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a duplicate account is rejected."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test that a YAML config is imported and a deprecation issue is created."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "user@example.com"
    assert result["data"] == {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: "secret",
    }

    issue_registry = hass.data["issue_registry"]
    assert issue_registry.async_get_issue(DOMAIN, "deprecated_yaml") is not None


async def test_import_flow_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that a duplicate YAML import is silently aborted."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_USERNAME: "user@example.com", CONF_PASSWORD: "secret"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_flow_api: AsyncMock,
    mock_schluter_api: AsyncMock,
) -> None:
    """Test successful reauthentication updates the password."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data[CONF_PASSWORD] == "new-password"


async def test_reauth_flow_unknown_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_flow_api: AsyncMock,
    mock_schluter_api: AsyncMock,
) -> None:
    """Test that an unexpected error in the reauth flow shows an unknown error."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_config_flow_api.async_get_session.side_effect = Exception("unexpected")
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "any-password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_config_flow_api: AsyncMock,
    mock_schluter_api: AsyncMock,
) -> None:
    """Test that an invalid password in the reauth flow shows an error."""
    await setup_integration(hass, mock_config_entry)

    result = await mock_config_entry.start_reauth_flow(hass)

    mock_config_flow_api.async_get_session.side_effect = InvalidCredentialsError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "wrong-password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}
