"""Test the zimi config flow."""


from homeassistant import config_entries, data_entry_flow
from homeassistant.components.zimi import DOMAIN
from homeassistant.core import HomeAssistant


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test initial config_flow."""

    flow = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(flow["flow_id"])

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["handler"] == DOMAIN
