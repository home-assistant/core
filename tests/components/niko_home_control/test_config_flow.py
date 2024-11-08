"""Test theDEFAULT_NAMEconfig flow."""

from unittest.mock import AsyncMock

from homeassistant.components.niko_home_control.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_full_flow(
    hass: HomeAssistant, mock_nhc: AsyncMock, mock_setup_entry: AsyncMock
) -> None:
    """Test the full flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "0.0.0.0"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    # assert result["title"] == "0.0.0.0"
    assert result["data"] == {CONF_HOST: "0.0.0.0"}

    assert len(mock_setup_entry.mock_calls) == 1
