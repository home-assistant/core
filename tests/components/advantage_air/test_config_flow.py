"""Test the Advantage Air config flow."""

from unittest.mock import AsyncMock, patch

from advantage_air import ApiError

from homeassistant import config_entries
from homeassistant.components.advantage_air.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import TEST_SYSTEM_DATA, USER_INPUT


async def test_form(hass: HomeAssistant) -> None:
    """Test that form shows up."""

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] is FlowResultType.FORM
    assert result1["step_id"] == "user"
    assert result1["errors"] == {}

    with (
        patch(
            "homeassistant.components.advantage_air.config_flow.advantage_air.async_get",
            new=AsyncMock(return_value=TEST_SYSTEM_DATA),
        ) as mock_get,
        patch(
            "homeassistant.components.advantage_air.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            USER_INPUT,
        )
        await hass.async_block_till_done()
        mock_setup_entry.assert_called_once()
        mock_get.assert_called_once()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "testname"
    assert result2["data"] == USER_INPUT

    # Test Duplicate Config Flow
    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.advantage_air.config_flow.advantage_air.async_get",
        new=AsyncMock(return_value=TEST_SYSTEM_DATA),
    ) as mock_get:
        result4 = await hass.config_entries.flow.async_configure(
            result3["flow_id"],
            USER_INPUT,
        )
    assert result4["type"] is FlowResultType.ABORT


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    with patch(
        "homeassistant.components.advantage_air.config_flow.advantage_air.async_get",
        new=AsyncMock(side_effect=ApiError),
    ) as mock_get:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
        mock_get.assert_called_once()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}
