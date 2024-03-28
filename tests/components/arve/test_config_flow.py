"""Test the Arve config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.arve.config_flow import ArveConnectionError
from homeassistant.components.arve.const import DOMAIN
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_CLIENT_SECRET
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import USER_INPUT

from tests.common import MockConfigEntry


async def create_entry(result, mock_setup_entry: AsyncMock):
    """Create test entry."""
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "Name of the device"
    assert result["data"] == USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "asyncarve.Arve.get_customer_id",
        side_effect=ArveConnectionError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_abort_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test form aborts if already configured."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ACCESS_TOKEN: "test-access-token",
            CONF_CLIENT_SECRET: "test-customer-token",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "already_configured"
