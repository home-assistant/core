"""Test the Axle configuration flow."""

from unittest.mock import AsyncMock, patch

from aioaxlevpp import AxleAuthenticationError, AxleConnectionError, AxleError
import pytest

from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user(hass: HomeAssistant) -> None:
    """Configure the feed through the UI."""
    result = await hass.config_entries.flow.async_init(
        "axle_energy", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    with patch(
        "homeassistant.components.axle_energy.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "test-token"}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_API_KEY: "test-token"}
    assert result["title"] == "Axle Energy"


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (AxleAuthenticationError(), "invalid_auth"),
        (AxleConnectionError(), "cannot_connect"),
        (AxleError(), "cannot_connect"),
    ],
)
async def test_user_errors(
    hass: HomeAssistant, mock_client: AsyncMock, error: Exception, message: str
) -> None:
    """Show recoverable setup failures."""
    mock_client.get_event.side_effect = error
    result = await hass.config_entries.flow.async_init(
        "axle_energy", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": message}
    mock_client.get_event.side_effect = None
    with patch(
        "homeassistant.components.axle_energy.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "replacement-token"}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_API_KEY: "replacement-token"}
    assert result["title"] == "Axle Energy"


async def test_duplicate(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    """Reject the same key without making another API request."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "axle_energy", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_client.get_event.assert_not_called()


async def test_multiple_entries(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: AsyncMock,
) -> None:
    """Allow another event feed with a different key."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        "axle_energy", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    with patch(
        "homeassistant.components.axle_energy.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_API_KEY: "another-token"}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {CONF_API_KEY: "another-token"}
    assert len(hass.config_entries.async_entries("axle_energy")) == 2
    assert mock_config_entry.data == {CONF_API_KEY: "test-token"}
    mock_client.get_event.assert_awaited_once()
