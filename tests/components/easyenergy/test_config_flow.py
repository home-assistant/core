"""Test the easyEnergy config flow."""
from unittest.mock import MagicMock

from homeassistant.components.easyenergy.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_full_user_flow(
    hass: HomeAssistant,
    mock_setup_entry: MagicMock,
) -> None:
    """Test the full user configuration flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert "flow_id" in result

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={},
    )

    assert result2.get("type") == FlowResultType.CREATE_ENTRY
    assert result2.get("title") == "easyEnergy"
    assert result2.get("data") == {}

    assert len(mock_setup_entry.mock_calls) == 1
