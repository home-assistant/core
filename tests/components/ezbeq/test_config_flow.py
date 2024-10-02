"""Tests for the ezbeq config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import ezbeq
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .conftest import mock_get_version
from .const import MOCK_CONFIG

pytestmark = pytest.mark.asyncio


async def test_full_flow(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        ezbeq.const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    # patch the connection test
    with patch(
        "pyezbeq.ezbeq.EzbeqClient.get_version",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCK_CONFIG[CONF_HOST],
                CONF_PORT: MOCK_CONFIG[CONF_PORT],
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1


async def test_fail_connection(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        ezbeq.const.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["errors"] == {}
    assert result["step_id"] == "user"

    # patch the connection test
    with patch(
        "pyezbeq.ezbeq.EzbeqClient.get_version",
        side_effect=mock_get_version,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: MOCK_CONFIG[CONF_HOST],
                CONF_PORT: MOCK_CONFIG[CONF_PORT],
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
