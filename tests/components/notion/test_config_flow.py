"""Define tests for the Notion config flow."""
from unittest.mock import AsyncMock, patch

from aionotion.errors import InvalidCredentialsError, NotionError
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.notion import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from .conftest import TEST_PASSWORD, TEST_USERNAME


@pytest.mark.parametrize(
    ("get_client_with_exception", "errors"),
    [
        (AsyncMock(side_effect=Exception), {"base": "unknown"}),
        (AsyncMock(side_effect=InvalidCredentialsError), {"base": "invalid_auth"}),
        (AsyncMock(side_effect=NotionError), {"base": "unknown"}),
    ],
)
async def test_create_entry(
    hass: HomeAssistant,
    client,
    config,
    errors,
    get_client_with_exception,
    mock_aionotion,
) -> None:
    """Test creating an etry (including recovery from errors)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test errors that can arise when getting a Notion API client:
    with patch(
        "homeassistant.components.notion.config_flow.async_get_client",
        get_client_with_exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=config
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == errors

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=config
    )
    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
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
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("get_client_with_exception", "errors"),
    [
        (AsyncMock(side_effect=Exception), {"base": "unknown"}),
        (AsyncMock(side_effect=InvalidCredentialsError), {"base": "invalid_auth"}),
        (AsyncMock(side_effect=NotionError), {"base": "unknown"}),
    ],
)
async def test_reauth(
    hass: HomeAssistant,
    config,
    config_entry,
    errors,
    get_client_with_exception,
    setup_config_entry,
) -> None:
    """Test that re-auth works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": SOURCE_REAUTH,
            "entry_id": config_entry.entry_id,
            "unique_id": config_entry.unique_id,
        },
        data=config,
    )
    assert result["step_id"] == "reauth_confirm"

    # Test errors that can arise when getting a Notion API client:
    with patch(
        "homeassistant.components.notion.config_flow.async_get_client",
        get_client_with_exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "password"}
        )
        assert result["type"] == data_entry_flow.FlowResultType.FORM
        assert result["errors"] == errors

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "password"}
    )
    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries()) == 1
