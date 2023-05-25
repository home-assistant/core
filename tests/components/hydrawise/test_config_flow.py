"""Test the Hydrawise config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from requests.exceptions import HTTPError

from homeassistant import config_entries
from homeassistant.components.hydrawise import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@patch("hydrawiser.core.Hydrawiser")
async def test_form(
    mock_api: MagicMock, hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "abc123"}
    )
    mock_api.return_value.status = "All good!"
    mock_api.return_value.customer_id = 12345
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Hydrawise"
    assert result2["data"] == {"api_key": "abc123"}
    assert len(mock_setup_entry.mock_calls) == 1


@patch("hydrawiser.core.Hydrawiser", side_effect=HTTPError)
async def test_form_api_error(mock_api: MagicMock, hass: HomeAssistant) -> None:
    """Test we handle API errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "abc123"}
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


@patch("hydrawiser.core.Hydrawiser")
async def test_form_no_status(mock_api: MagicMock, hass: HomeAssistant) -> None:
    """Test we handle API errors."""
    mock_api.return_value.status = None
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "abc123"}
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
