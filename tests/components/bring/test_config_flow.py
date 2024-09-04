"""Test the Bring! config flow."""

from unittest.mock import AsyncMock

from bring_api.exceptions import (
    BringAuthException,
    BringParseException,
    BringRequestException,
)
import pytest

from homeassistant.components.bring.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
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
        DOMAIN, context={"source": SOURCE_USER}
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
    assert result["title"] == "Bring"
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
        DOMAIN, context={"source": SOURCE_USER}
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
    assert result["result"].title == "Bring"

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


async def test_flow_reauth(
    hass: HomeAssistant,
    mock_bring_client: AsyncMock,
    bring_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow."""

    bring_config_entry.add_to_hass(hass)

    result = await bring_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "new-email", CONF_PASSWORD: "new-password"},
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert bring_config_entry.data == {
        CONF_EMAIL: "new-email",
        CONF_PASSWORD: "new-password",
    }
    assert len(hass.config_entries.async_entries()) == 1


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (BringRequestException(), "cannot_connect"),
        (BringAuthException(), "invalid_auth"),
        (BringParseException(), "unknown"),
        (IndexError(), "unknown"),
    ],
)
async def test_flow_reauth_error_and_recover(
    hass: HomeAssistant,
    mock_bring_client: AsyncMock,
    bring_config_entry: MockConfigEntry,
    raise_error,
    text_error,
) -> None:
    """Test reauth flow."""

    bring_config_entry.add_to_hass(hass)

    result = await bring_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    mock_bring_client.login.side_effect = raise_error
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "new-email", CONF_PASSWORD: "new-password"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": text_error}

    mock_bring_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_EMAIL: "new-email", CONF_PASSWORD: "new-password"},
    )

    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1
