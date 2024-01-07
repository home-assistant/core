"""Test the Bring! config flow."""
from unittest.mock import AsyncMock, Mock, patch

import pytest
from python_bring_api.exceptions import (
    BringAuthException,
    BringParseException,
    BringRequestException,
)

from homeassistant import config_entries
from homeassistant.components.bring.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_DATA_STEP = {
    CONF_EMAIL: "email@server",
    CONF_PASSWORD: "password",
}


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.bring.config_flow.Bring.login",
        autospec=True,
        return_value=True,
    ), patch(
        "homeassistant.components.bring.config_flow.Bring.loadLists",
        autospec=True,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_STEP,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "email"
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
    hass: HomeAssistant, raise_error, text_error
) -> None:
    """Test unknown errors."""
    with patch(
        "homeassistant.components.bring.config_flow.Bring.login",
        autospec=True,
        side_effect=raise_error,
    ) as mock_Bring, patch(
        "homeassistant.components.bring.config_flow.Bring.loadLists",
        autospec=True,
        return_value=True,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_STEP,
        )

        assert result["type"] == "form"
        assert result["errors"]["base"] == text_error

        # Recover
        mock_Bring.side_effect = None
        mock_Bring.return_value = True
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_STEP,
        )

        assert result["type"] == "create_entry"
        assert result["result"].title == "email"

        assert result["data"] == MOCK_DATA_STEP


async def test_flow_user_init_data_already_configured(hass: HomeAssistant) -> None:
    """Test we abort user data set when entry is already configured."""

    with patch(
        "homeassistant.components.bring.config_flow.Bring",
        return_value=Mock(),
    ) as mock_bring:
        mock_bring().uuid = "UNIQUE"

        entry = MockConfigEntry(domain=DOMAIN, data=MOCK_DATA_STEP, unique_id="UNIQUE")
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=MOCK_DATA_STEP,
        )

        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"
