"""Tests for the Mitsubishi-Climaveneta iMXW config flow."""
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.climaveneta_imxw.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.climaveneta_imxw.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.climaveneta_imxw.config_flow.get_hub",
        return_value=True,
    ) as mock_get_hub:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "hub": "modbus_hub",
                "slave": 1,
                "name": "test-name",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Climaveneta_IMXW test-name at modbus_hub:1"
    assert result2["data"] == {
        "hub": "modbus_hub",
        "slave": 1,
        "name": "test-name",
    }
    assert len(mock_get_hub.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_wrong_modbus_hub(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle the non existent modbus hub error."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.climaveneta_imxw.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.climaveneta_imxw.config_flow.get_hub",
        side_effect=KeyError,
    ) as mock_get_hub:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "hub": "modbus_hub",
                "slave": 1,
                "name": "test-name",
            },
        )
        await hass.async_block_till_done()

    assert result2["errors"] == {"hub": "invalid_modbus_hub"}
    assert result2["type"] == FlowResultType.FORM

    assert len(mock_get_hub.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 0
