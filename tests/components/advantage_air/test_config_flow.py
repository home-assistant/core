"""Test the Advantage Air config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.advantage_air.const import DOMAIN
from homeassistant.core import HomeAssistant

from . import TEST_SYSTEM_DATA, TEST_SYSTEM_URL, USER_INPUT

from tests.test_util.aiohttp import AiohttpClientMocker


async def test_form(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test that form shows up."""

    aioclient_mock.get(
        TEST_SYSTEM_URL,
        text=TEST_SYSTEM_DATA,
    )

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == data_entry_flow.FlowResultType.FORM
    assert result1["step_id"] == "user"
    assert result1["errors"] == {}

    with patch(
        "homeassistant.components.advantage_air.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result1["flow_id"],
            USER_INPUT,
        )

    assert len(aioclient_mock.mock_calls) == 1
    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result2["title"] == "testname"
    assert result2["data"] == USER_INPUT
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1

    # Test Duplicate Config Flow
    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result4 = await hass.config_entries.flow.async_configure(
        result3["flow_id"],
        USER_INPUT,
    )
    assert result4["type"] == data_entry_flow.FlowResultType.ABORT


async def test_form_cannot_connect(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test we handle cannot connect error."""

    aioclient_mock.get(
        TEST_SYSTEM_URL,
        exc=SyntaxError,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["step_id"] == "user"
    assert result2["errors"] == {"base": "cannot_connect"}
    assert len(aioclient_mock.mock_calls) == 1
