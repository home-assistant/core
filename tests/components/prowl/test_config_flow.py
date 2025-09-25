"""Test Prowl config flow."""

from unittest.mock import Mock

import prowlpy
import pytest

from homeassistant import config_entries
from homeassistant.components.prowl.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import (
    BAD_API_RESPONSE,
    CONF_INPUT,
    INVALID_API_KEY_ERROR,
    OTHER_API_KEY,
    TIMEOUT_ERROR,
)

from tests.common import MockConfigEntry


async def test_flow_user(hass: HomeAssistant, mock_prowlpy: Mock) -> None:
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )

    assert mock_prowlpy.verify_key.call_count > 0
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == CONF_INPUT[CONF_NAME]
    assert result["data"] == {CONF_API_KEY: CONF_INPUT[CONF_API_KEY]}


async def test_flow_user_bad_key(hass: HomeAssistant, mock_prowlpy: Mock) -> None:
    """Test user submitting a bad API key."""
    mock_prowlpy.verify_key.side_effect = prowlpy.APIError("Invalid API key")

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )

    assert mock_prowlpy.verify_key.call_count > 0
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == INVALID_API_KEY_ERROR


async def test_flow_user_prowl_timeout(hass: HomeAssistant, mock_prowlpy: Mock) -> None:
    """Test Prowl API timeout."""
    mock_prowlpy.verify_key.side_effect = TimeoutError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )

    assert mock_prowlpy.verify_key.call_count > 0
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == TIMEOUT_ERROR


async def test_flow_api_failure(hass: HomeAssistant, mock_prowlpy: Mock) -> None:
    """Test Prowl API failure."""
    mock_prowlpy.verify_key.side_effect = prowlpy.APIError(BAD_API_RESPONSE)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=CONF_INPUT,
    )

    assert mock_prowlpy.verify_key.call_count > 0
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == BAD_API_RESPONSE


@pytest.fixure("mock_prowlpy")
async def test_flow_reauth(
    hass: HomeAssistant, mock_prowlpy_config_entry: MockConfigEntry
) -> None:
    """Test the reauth flow."""
    mock_prowlpy_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_prowlpy_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_prowlpy_config_entry.entry_id,
        },
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_KEY: OTHER_API_KEY},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_prowlpy_config_entry.data[CONF_API_KEY] == OTHER_API_KEY
