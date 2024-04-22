"""Test the Hydrawise config flow."""

from unittest.mock import AsyncMock

from aiohttp import ClientError
from pydrawise.schema import User
import pytest

from homeassistant import config_entries
from homeassistant.components.hydrawise.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_pydrawise: AsyncMock,
    user: User,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"api_key": "abc123"}
    )
    mock_pydrawise.get_user.return_value = user
    await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Hydrawise"
    assert result2["data"] == {"api_key": "abc123"}
    assert len(mock_setup_entry.mock_calls) == 1
    mock_pydrawise.get_user.assert_called_once_with(fetch_zones=False)


async def test_form_api_error(
    hass: HomeAssistant, mock_pydrawise: AsyncMock, user: User
) -> None:
    """Test we handle API errors."""
    mock_pydrawise.get_user.side_effect = ClientError("XXX")

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    data = {"api_key": "abc123"}
    result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], data
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_pydrawise.get_user.reset_mock(side_effect=True)
    mock_pydrawise.get_user.return_value = user
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result2["type"] is FlowResultType.CREATE_ENTRY


async def test_form_connect_timeout(
    hass: HomeAssistant, mock_pydrawise: AsyncMock, user: User
) -> None:
    """Test we handle API errors."""
    mock_pydrawise.get_user.side_effect = TimeoutError
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    data = {"api_key": "abc123"}
    result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], data
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "timeout_connect"}

    mock_pydrawise.get_user.reset_mock(side_effect=True)
    mock_pydrawise.get_user.return_value = user
    result2 = await hass.config_entries.flow.async_configure(result["flow_id"], data)
    assert result2["type"] is FlowResultType.CREATE_ENTRY
