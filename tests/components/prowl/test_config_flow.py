"""Test Prowl config flow."""

import pytest

from homeassistant import config_entries
from homeassistant.components.prowl.const import DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import BAD_API_RESPONSE, CONF_INPUT, INVALID_API_KEY_ERROR, TIMEOUT_ERROR


@pytest.mark.asyncio
async def test_flow_user(hass: HomeAssistant, mock_pyprowl_success) -> None:
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )

    assert mock_pyprowl_success.verify_key.call_count > 0
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == CONF_INPUT[CONF_NAME]
    assert result["data"] == CONF_INPUT


@pytest.mark.asyncio
async def test_flow_user_bad_key(hass: HomeAssistant, mock_pyprowl_forbidden) -> None:
    """Test user submitting a bad API key."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )

    assert mock_pyprowl_forbidden.verify_key.call_count > 0
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == INVALID_API_KEY_ERROR


@pytest.mark.asyncio
async def test_flow_user_prowl_timeout(
    hass: HomeAssistant, mock_pyprowl_timeout
) -> None:
    """Test Prowl API timeout."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )

    assert mock_pyprowl_timeout.verify_key.call_count > 0
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == TIMEOUT_ERROR


@pytest.mark.asyncio
async def test_flow_api_failure(hass: HomeAssistant, mock_pyprowl_fail) -> None:
    """Test Prowl API failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )

    assert mock_pyprowl_fail.verify_key.call_count > 0
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == BAD_API_RESPONSE
