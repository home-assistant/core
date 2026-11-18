"""Test the WATERCryst BIOCAT config flow."""

from unittest.mock import AsyncMock

from pyocat import (
    WTCApiCancelledError,
    WTCApiDisabledError,
    WTCApiQuotaExceededError,
    WTCApiRequestError,
    WTCApiServerError,
    WTCApiTimeoutError,
    WTCApiUnauthorizedError,
    WTCApiValidationError,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.watercryst.const import DOMAIN
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import BIOCAT_SERIAL, DEVICE_NAME


@pytest.mark.usefixtures("mock_api_client")
async def test_form_full_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test successful flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "<api-key>",
        },
    )
    await hass.async_block_till_done()

    assert result["result"].unique_id == BIOCAT_SERIAL
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEVICE_NAME
    assert result["data"] == {
        CONF_API_KEY: "<api-key>",
    }
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_api_client")
async def test_duplicate_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test duplicate entry handling."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "<api-key>",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "error"),
    [
        (WTCApiCancelledError(), "cannot_connect"),
        (WTCApiUnauthorizedError(), "invalid_auth"),
        (WTCApiDisabledError(), "api_disabled"),
        (WTCApiQuotaExceededError(), "cannot_connect"),
        (WTCApiRequestError(), "cannot_connect"),
        (WTCApiServerError(), "cannot_connect"),
        (WTCApiTimeoutError(), "cannot_connect"),
        (WTCApiValidationError(), "cannot_connect"),
        (Exception(), "unknown"),
    ],
)
async def test_form_raise_error(
    hass: HomeAssistant,
    mock_api_client: AsyncMock,
    mock_setup_entry: AsyncMock,
    exception: Exception,
    error: str,
) -> None:
    """Test config flow error handling."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_api_client.get_device_info.side_effect = exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "<api-key>",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_api_client.get_device_info.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "<api-key>",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEVICE_NAME
    assert result["data"] == {
        CONF_API_KEY: "<api-key>",
    }

    mock_setup_entry.assert_awaited_once()
    mock_api_client.get_state.assert_not_awaited()


async def test_form_missing_biocat_serial(
    hass: HomeAssistant, mock_api_client: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test config flow for missing biocat serial."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    mock_api_client.get_device_info.return_value.biocat_serial = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "<api-key>",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_api_client.get_device_info.return_value.biocat_serial = BIOCAT_SERIAL

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_KEY: "<api-key>",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == DEVICE_NAME
    assert result["data"] == {
        CONF_API_KEY: "<api-key>",
    }
