"""Define tests for the Tile config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from pytile.errors import InvalidAuthError, TileError

from homeassistant.components.tile import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_PASSWORD, TEST_USERNAME

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("mock_login_response", "errors"),
    [
        (AsyncMock(side_effect=InvalidAuthError), {"base": "invalid_auth"}),
        (AsyncMock(side_effect=TileError), {"base": "unknown"}),
    ],
)
async def test_create_entry(
    hass: HomeAssistant, api, config, errors, mock_login_response, mock_pytile
) -> None:
    """Test creating an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test errors that can arise:
    with patch(
        "homeassistant.components.tile.config_flow.async_login", mock_login_response
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=config
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"
        assert result["errors"] == errors

    # Test that we can recover from login errors:
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_USERNAME
    assert result["data"] == {
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }


async def test_duplicate_error(hass: HomeAssistant, config, setup_config_entry) -> None:
    """Test that errors are shown when duplicates are added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=config
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_entry(hass: HomeAssistant, config, mock_pytile) -> None:
    """Test importing an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=config
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_USERNAME
    assert result["data"] == {
        CONF_USERNAME: TEST_USERNAME,
        CONF_PASSWORD: TEST_PASSWORD,
    }


async def test_step_reauth(
    hass: HomeAssistant, config, config_entry: MockConfigEntry, setup_config_entry
) -> None:
    """Test that the reauth step works."""
    result = await config_entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "password"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries()) == 1
