"""Test the Data Grand Lyon config flow."""

from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectionError, ClientResponseError
import pytest

from homeassistant import config_entries
from homeassistant.components.data_grandlyon.const import (
    CONF_LINE,
    CONF_STOP_ID,
    DOMAIN,
    SUBENTRY_TYPE_STOP,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

# Main config flow tests


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form and can create an entry with credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Data Grand Lyon"
    assert result["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we show an error when the API is unreachable."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        side_effect=ClientConnectionError(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Recover
    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test we abort if already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: "user", CONF_PASSWORD: "pass"}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# Stop subentry tests


@pytest.mark.parametrize("mock_subentries", [[]])
async def test_stop_subentry_flow(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test adding a stop subentry."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": config_entries.SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LINE: "C3", CONF_STOP_ID: 456},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "C3 - Stop 456"
    assert result["data"] == {CONF_LINE: "C3", CONF_STOP_ID: 456}
    assert result["unique_id"] == "C3_456"


async def test_stop_subentry_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test stop subentry aborts if same line+stop already exists."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (mock_config_entry.entry_id, SUBENTRY_TYPE_STOP),
        context={"source": config_entries.SOURCE_USER},
    )

    result = await hass.config_entries.subentries.async_configure(
        result["flow_id"],
        {CONF_LINE: "C3", CONF_STOP_ID: 100},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


# Error type differentiation tests


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we show invalid_auth on 401 response."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        side_effect=ClientResponseError(None, None, status=401),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "wrong"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we show unknown on unexpected exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        side_effect=RuntimeError("unexpected"),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


async def test_form_http_error_non_auth(hass: HomeAssistant) -> None:
    """Test we show cannot_connect on non-auth HTTP errors (e.g. 500)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.data_grandlyon.config_flow.DataGrandLyonClient.get_tcl_passages",
        side_effect=ClientResponseError(None, None, status=500),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_USERNAME: "user", CONF_PASSWORD: "pass"},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
