"""Test the Cielo Home config flow."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final
from unittest.mock import AsyncMock, patch

from cieloconnectapi.exceptions import AuthenticationError
import pytest

from homeassistant.components.cielo_home.const import (
    DOMAIN,
    NoDevicesError,
    NoUsernameError,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult, FlowResultType

from tests.common import MockConfigEntry

TEST_API_KEY: Final = "test-api-key"
TEST_TOKEN: Final = "validated-auth-token"
TEST_TITLE_MASKED: Final = (
    f"Cielo Home ({TEST_API_KEY[:4]}*****************{TEST_API_KEY[-4:]})"
)

MOCK_AUTH_PATH: Final = (
    "homeassistant.components.cielo_home.config_flow.CieloClient.get_or_refresh_token"
)


async def test_full_config_flow_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test successful configuration from user step."""
    result: FlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert isinstance(result, Mapping)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(MOCK_AUTH_PATH, return_value=TEST_TOKEN):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_API_KEY: TEST_API_KEY},
        )
        await hass.async_block_till_done()

    assert isinstance(result, Mapping)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == TEST_TITLE_MASKED
    assert result["data"] == {
        CONF_API_KEY: TEST_API_KEY,
        CONF_TOKEN: TEST_TOKEN,
    }

    entry = hass.config_entries.async_entries(DOMAIN)[0]
    assert entry.unique_id == TEST_API_KEY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_full_config_flow_abort_already_configured(hass: HomeAssistant) -> None:
    """Test aborting when the unique ID is already configured."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_API_KEY: TEST_API_KEY, CONF_TOKEN: TEST_TOKEN},
        unique_id=TEST_API_KEY,
    )
    entry.add_to_hass(hass)

    # Initiate the flow
    result: FlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert isinstance(result, Mapping)
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


@pytest.mark.parametrize(
    ("api_error", "flow_error_key"),
    [
        (AuthenticationError, "invalid_auth"),
        (ConnectionError, "cannot_connect"),
        (NoDevicesError, "no_devices"),
        (NoUsernameError, "no_username"),
        (Exception, "unknown"),
    ],
)
async def test_form_error_mapping(
    hass: HomeAssistant, api_error: Exception, flow_error_key: str
) -> None:
    """Test we handle various API errors correctly."""

    result: FlowResult = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert isinstance(result, Mapping)
    assert result["type"] is FlowResultType.FORM

    with patch(MOCK_AUTH_PATH, side_effect=api_error):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: TEST_API_KEY}
        )

    assert isinstance(result, Mapping)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": flow_error_key}

    with patch(MOCK_AUTH_PATH, return_value=TEST_TOKEN):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: TEST_API_KEY}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
