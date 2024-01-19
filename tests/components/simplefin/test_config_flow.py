"""Test config flow.""" ""
from homeassistant import config_entries
from homeassistant.components.simplefin import DOMAIN
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_standard_config_flow(
    hass: HomeAssistant,
    mock_claim_setup_token: str,
):
    """Test standard config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_API_TOKEN: "donJulio"},
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
