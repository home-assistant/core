"""Test the Axle configuration flow."""

from unittest.mock import AsyncMock

from aioaxlevpp import AxleAuthenticationError, AxleConnectionError, AxleError
import pytest

from homeassistant.components.axle_energy.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_user(hass: HomeAssistant) -> None:
    """Configure the feed through the UI."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
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
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-token"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": message}
    mock_client.get_event.side_effect = None
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
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_API_KEY: "test-token"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    mock_client.get_event.assert_not_called()
