"""Define tests for the Meater config flow."""

from unittest.mock import AsyncMock

from meater import AuthenticationError, ServiceUnavailableError
import pytest

from homeassistant.components.meater.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_meater_client: AsyncMock
) -> None:
    """Test that the user flow works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_USERNAME: "user@host.com",
        CONF_PASSWORD: "password123",
    }
    assert result["result"].unique_id == "user@host.com"
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (AuthenticationError, "invalid_auth"),
        (ServiceUnavailableError, "service_unavailable_error"),
        (Exception, "unknown_auth_error"),
    ],
)
async def test_user_flow_exceptions(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_meater_client: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test that an invalid API/App Key throws an error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_meater_client.authenticate.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    mock_meater_client.authenticate.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meater_client: AsyncMock,
) -> None:
    """Test that errors are shown when duplicates are added."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "user@host.com", CONF_PASSWORD: "password123"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_meater_client: AsyncMock,
) -> None:
    """Test that the reauth flow works."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "passwordabc"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_USERNAME: "user@host.com",
        CONF_PASSWORD: "passwordabc",
    }
