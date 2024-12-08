"""Test the Cookidoo config flow."""

from unittest.mock import AsyncMock

from cookidoo_api.exceptions import (
    CookidooAuthException,
    CookidooException,
    CookidooRequestException,
)
import pytest

from homeassistant.components.cookidoo.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_COUNTRY, CONF_EMAIL, CONF_LANGUAGE, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import COUNTRY, EMAIL, LANGUAGE, PASSWORD

from tests.common import MockConfigEntry

MOCK_DATA_USER_STEP = {
    CONF_EMAIL: EMAIL,
    CONF_PASSWORD: PASSWORD,
    CONF_COUNTRY: COUNTRY,
}

MOCK_DATA_LANGUAGE_STEP = {
    CONF_LANGUAGE: LANGUAGE,
}


async def test_flow_user_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_cookidoo_client: AsyncMock
) -> None:
    """Test we get the user flow and create entry with success."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["handler"] == "cookidoo"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_USER_STEP,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "language"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_LANGUAGE_STEP,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Cookidoo"
    assert result["data"] == {**MOCK_DATA_USER_STEP, **MOCK_DATA_LANGUAGE_STEP}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (CookidooRequestException(), "cannot_connect"),
        (CookidooAuthException(), "invalid_auth"),
        (CookidooException(), "unknown"),
        (IndexError(), "unknown"),
    ],
)
async def test_flow_user_init_data_unknown_error_and_recover_on_step_1(
    hass: HomeAssistant,
    mock_cookidoo_client: AsyncMock,
    raise_error: Exception,
    text_error: str,
) -> None:
    """Test unknown errors."""
    mock_cookidoo_client.login.side_effect = raise_error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_USER_STEP,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == text_error

    # Recover
    mock_cookidoo_client.login.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_USER_STEP,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "language"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_LANGUAGE_STEP,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].title == "Cookidoo"

    assert result["data"] == {**MOCK_DATA_USER_STEP, **MOCK_DATA_LANGUAGE_STEP}


@pytest.mark.parametrize(
    ("raise_error", "text_error"),
    [
        (CookidooRequestException(), "cannot_connect"),
        (CookidooAuthException(), "invalid_auth"),
        (CookidooException(), "unknown"),
        (IndexError(), "unknown"),
    ],
)
async def test_flow_user_init_data_unknown_error_and_recover_on_step_2(
    hass: HomeAssistant,
    mock_cookidoo_client: AsyncMock,
    raise_error: Exception,
    text_error: str,
) -> None:
    """Test unknown errors."""
    mock_cookidoo_client.get_additional_items.side_effect = raise_error

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_USER_STEP,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "language"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_LANGUAGE_STEP,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == text_error

    # Recover
    mock_cookidoo_client.get_additional_items.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_LANGUAGE_STEP,
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].title == "Cookidoo"

    assert result["data"] == {**MOCK_DATA_USER_STEP, **MOCK_DATA_LANGUAGE_STEP}


async def test_flow_user_init_data_already_configured(
    hass: HomeAssistant,
    mock_cookidoo_client: AsyncMock,
    cookidoo_config_entry: MockConfigEntry,
) -> None:
    """Test we abort user data set when entry is already configured."""

    cookidoo_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_DATA_USER_STEP,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
