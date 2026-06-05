"""Test the Aqvify config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponseError
from pyaqvify import AqvifyAccount, AqvifyAuthException
import pytest

from homeassistant import config_entries
from homeassistant.components.aqvify.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_aqvify_client: MagicMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "test-api-key",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Aqvify"
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error_base"),
    [
        (AqvifyAuthException, "invalid_auth"),
        (
            ClientResponseError(request_info=None, history=None, status=500),
            "cannot_connect",
        ),
        (TypeError, "unknown"),
    ],
)
async def test_form_invalid(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    side_effect: Exception,
    error_base: str,
) -> None:
    """Test we handle errors during form submission."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.aqvify.config_flow.AqvifyAPI.async_get_account_id",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "test-api-key",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_base}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "homeassistant.components.aqvify.config_flow.AqvifyAPI.async_get_account_id",
        return_value=AqvifyAccount({"accountId": "ABC123"}),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "test-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Aqvify"
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_same_account_setup(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_aqvify_client: MagicMock
) -> None:
    """Test setup same account twice."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "test-api-key",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Aqvify"
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    # Setup config entry with same account.

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "test-api-key2",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_second_account_setup(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test setup second account."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aqvify.config_flow.AqvifyAPI.async_get_account_id",
        return_value=AqvifyAccount({"accountId": "FirstAccount"}),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "test-api-key",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Aqvify"
    assert result["data"] == {
        CONF_API_KEY: "test-api-key",
    }
    assert len(mock_setup_entry.mock_calls) == 1

    # Setup config entry with second account.

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aqvify.config_flow.AqvifyAPI.async_get_account_id",
        return_value=AqvifyAccount({"accountId": "SecondAccount"}),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_API_KEY: "test-api-key-2",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Aqvify"
    assert result["data"] == {
        CONF_API_KEY: "test-api-key-2",
    }
    assert len(mock_setup_entry.mock_calls) == 2
