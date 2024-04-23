"""Test the Bring! config flow."""

from unittest.mock import AsyncMock

from bring_api.exceptions import (
    BringAuthException,
    BringParseException,
    BringRequestException,
)
import pytest

from homeassistant import config_entries
from homeassistant.components.bring.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import EMAIL, PASSWORD

from tests.common import MockConfigEntry

MOCK_DATA_STEP = {
    CONF_EMAIL: EMAIL,
    CONF_PASSWORD: PASSWORD,
}


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_bring_client: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_STEP,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_DATA_STEP["email"]
    assert result["data"] == MOCK_DATA_STEP
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (BringRequestException(), "cannot_connect"),
        (BringAuthException(), "invalid_auth"),
        (BringParseException(), "unknown"),
        (IndexError(), "unknown"),
    ],
)
async def test_flow_user_init_data_unknown_error_and_recover(
    hass: HomeAssistant, mock_bring_client: AsyncMock, raise_error, text_error
) -> None:
    """Test unknown errors."""
    mock_bring_client.login.side_effect = raise_error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_STEP,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == text_error

    # Recover
    mock_bring_client.login.side_effect = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_STEP,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].title == MOCK_DATA_STEP["email"]

    assert result["data"] == MOCK_DATA_STEP


async def test_flow_user_init_data_already_configured(
    hass: HomeAssistant,
    mock_bring_client: AsyncMock,
    bring_config_entry: MockConfigEntry,
) -> None:
    """Test we abort user data set when entry is already configured."""

    bring_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_STEP,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
