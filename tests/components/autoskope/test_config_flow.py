"""Test Autoskope config flow."""

from unittest.mock import AsyncMock

from autoskope_client.models import CannotConnect, InvalidAuth
import pytest

from homeassistant.components.autoskope.const import (
    DEFAULT_HOST,
    DOMAIN,
    SECTION_ADVANCED_SETTINGS,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_USERNAME: "test_user",
    CONF_PASSWORD: "test_password",
    SECTION_ADVANCED_SETTINGS: {
        CONF_HOST: DEFAULT_HOST,
    },
}


async def test_full_flow(
    hass: HomeAssistant,
    mock_autoskope_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test full user config flow from form to entry creation."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Autoskope (test_user)"
    assert result["data"] == {
        CONF_USERNAME: "test_user",
        CONF_PASSWORD: "test_password",
        CONF_HOST: DEFAULT_HOST,
    }
    assert result["result"].unique_id == f"test_user@{DEFAULT_HOST}"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (InvalidAuth("Invalid credentials"), "invalid_auth"),
        (CannotConnect("Connection failed"), "cannot_connect"),
    ],
)
async def test_flow_errors(
    hass: HomeAssistant,
    mock_autoskope_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test config flow error handling with recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    mock_autoskope_client.__aenter__.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    # Recovery: clear the error and retry
    mock_autoskope_client.__aenter__.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_flow_invalid_url(
    hass: HomeAssistant,
    mock_autoskope_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test config flow rejects invalid URL with recovery."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            SECTION_ADVANCED_SETTINGS: {
                CONF_HOST: "not-a-valid-url",
            },
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url"}

    # Recovery: provide a valid URL
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_autoskope_client: AsyncMock,
) -> None:
    """Test aborting if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_custom_host(
    hass: HomeAssistant,
    mock_autoskope_client: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test config flow with a custom white-label host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            SECTION_ADVANCED_SETTINGS: {
                CONF_HOST: "https://custom.autoskope.server",
            },
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "https://custom.autoskope.server"
    assert result["result"].unique_id == "test_user@https://custom.autoskope.server"
