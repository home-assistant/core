"""Test the Appwrite config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.appwrite.const import CONF_PROJECT_ID, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.appwrite.AppwriteClient.async_validate_credentials",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "http://appwrite.url",
                CONF_PROJECT_ID: "appwrite-project-id",
                CONF_API_KEY: "appwrite-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert (
        result["title"]
        == f'{result['data'][CONF_HOST]} - {result['data'][CONF_PROJECT_ID]}'
    )
    assert result["data"] == {
        CONF_HOST: "http://appwrite.url",
        CONF_PROJECT_ID: "appwrite-project-id",
        CONF_API_KEY: "appwrite-api-key",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_credentials(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.appwrite.AppwriteClient.async_validate_credentials",
        return_value=False,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "http://appwrite.url",
                CONF_PROJECT_ID: "appwrite-project-id",
                CONF_API_KEY: "appwrite-api-key",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "homeassistant.components.appwrite.AppwriteClient.async_validate_credentials",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "http://appwrite.url",
                CONF_PROJECT_ID: "appwrite-project-id",
                CONF_API_KEY: "appwrite-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert (
        result["title"]
        == f'{result['data'][CONF_HOST]} - {result['data'][CONF_PROJECT_ID]}'
    )
    assert result["data"] == {
        CONF_HOST: "http://appwrite.url",
        CONF_PROJECT_ID: "appwrite-project-id",
        CONF_API_KEY: "appwrite-api-key",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_url(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid url."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.appwrite.AppwriteClient.async_validate_credentials",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "appwrite",
                CONF_PROJECT_ID: "appwrite-project-id",
                CONF_API_KEY: "appwrite-api-key",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "homeassistant.components.appwrite.AppwriteClient.async_validate_credentials",
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "http://appwrite.url",
                CONF_PROJECT_ID: "appwrite-project-id",
                CONF_API_KEY: "appwrite-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert (
        result["title"]
        == f'{result['data'][CONF_HOST]} - {result['data'][CONF_PROJECT_ID]}'
    )
    assert result["data"] == {
        CONF_HOST: "http://appwrite.url",
        CONF_PROJECT_ID: "appwrite-project-id",
        CONF_API_KEY: "appwrite-api-key",
    }
    assert len(mock_setup_entry.mock_calls) == 1
