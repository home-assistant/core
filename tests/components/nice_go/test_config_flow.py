"""Test the Nice G.O. config flow."""

from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from nice_go import AuthFailedError
import pytest

from homeassistant.components.nice_go.const import (
    CONF_REFRESH_TOKEN,
    CONF_REFRESH_TOKEN_CREATION_TIME,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import setup_integration

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_setup_entry: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-email",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-email"
    assert result["data"][CONF_EMAIL] == "test-email"
    assert result["data"][CONF_PASSWORD] == "test-password"
    assert result["data"][CONF_REFRESH_TOKEN] == "test-refresh-token"
    assert CONF_REFRESH_TOKEN_CREATION_TIME in result["data"]
    assert result["result"].unique_id == "test-email"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [(AuthFailedError, "invalid_auth"), (Exception, "unknown")],
)
async def test_form_exceptions(
    hass: HomeAssistant,
    mock_nice_go: AsyncMock,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test we handle invalid auth."""
    mock_nice_go.authenticate.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-email",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    mock_nice_go.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-email",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nice_go: AsyncMock,
) -> None:
    """Test that duplicate devices are handled."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-email",
            CONF_PASSWORD: "test-password",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nice_go: AsyncMock,
) -> None:
    """Test reauth flow."""

    await setup_integration(hass, mock_config_entry, [])

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-email",
            CONF_PASSWORD: "other-fake-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [(AuthFailedError, "invalid_auth"), (Exception, "unknown")],
)
async def test_reauth_exceptions(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nice_go: AsyncMock,
    side_effect: Exception,
    expected_error: str,
) -> None:
    """Test we handle invalid auth."""
    mock_nice_go.authenticate.side_effect = side_effect
    await setup_integration(hass, mock_config_entry, [])

    result = await mock_config_entry.start_reauth_flow(hass)

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-email",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}
    mock_nice_go.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_EMAIL: "test-email",
            CONF_PASSWORD: "test-password",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries()) == 1
