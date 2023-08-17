"""Test the Hong Kong Observatory config flow."""

from homeassistant.components.hko.const import DEFAULT_LOCATION, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_LOCATION
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_user_flow(
    hass: HomeAssistant,
) -> None:
    """Test user config flow with minimum fields."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert "flow_id" in result

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_LOCATION: DEFAULT_LOCATION},
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == DEFAULT_LOCATION
    assert result["result"].unique_id == DEFAULT_LOCATION
    assert result["data"][CONF_LOCATION] == DEFAULT_LOCATION
