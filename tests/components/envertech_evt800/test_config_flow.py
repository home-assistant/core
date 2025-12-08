"""Test the Envertech EVT800 config flow."""

from unittest.mock import AsyncMock

from homeassistant.components.envertech_evt800.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import MOCK_USER_INPUT

from tests.conftest import MockConfigEntry


async def test_form(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_evt800_client: AsyncMock
) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        MOCK_USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USER_INPUT["host"]
    assert result["data"] == MOCK_USER_INPUT

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_already_configured(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_evt800_client: AsyncMock
) -> None:
    """Test starting a flow by user when already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT, unique_id="123456789")
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
