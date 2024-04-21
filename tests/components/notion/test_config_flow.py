"""Define tests for the Notion config flow."""

from unittest.mock import AsyncMock, patch

from aionotion.errors import InvalidCredentialsError, NotionError
import pytest

from homeassistant.components.notion import CONF_REFRESH_TOKEN, CONF_USER_UUID, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import TEST_PASSWORD, TEST_REFRESH_TOKEN, TEST_USER_UUID, TEST_USERNAME

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


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
    errors,
    get_client_with_exception,
    mock_aionotion,
) -> None:
    """Test creating an etry (including recovery from errors)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    # Test errors that can arise when getting a Notion API client:
    with patch(
        "homeassistant.components.notion.config_flow.async_get_client_with_credentials",
        get_client_with_exception,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_USERNAME: TEST_USERNAME,
                CONF_PASSWORD: TEST_PASSWORD,
            },
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == errors

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: TEST_USERNAME,
            CONF_PASSWORD: TEST_PASSWORD,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_USERNAME
    assert result["data"] == {
        CONF_REFRESH_TOKEN: TEST_REFRESH_TOKEN,
        CONF_USERNAME: TEST_USERNAME,
        CONF_USER_UUID: TEST_USER_UUID,
    }


async def test_duplicate_error(hass: HomeAssistant, config, config_entry) -> None:
    """Test that errors are shown when duplicates are added."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=config
    )
    assert result["type"] is FlowResultType.ABORT
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
    mock_aionotion,
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
        "homeassistant.components.notion.config_flow.async_get_client_with_credentials",
        get_client_with_exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_PASSWORD: "password"}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["errors"] == errors

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_PASSWORD: "password"}
    )
    # Block to ensure the setup_config_entry fixture does not
    # get undone before hass is shutdown so we do not try
    # to setup the config entry via reload.
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert len(hass.config_entries.async_entries()) == 1
