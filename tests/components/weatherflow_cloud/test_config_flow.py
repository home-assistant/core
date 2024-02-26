"""Test the WeatherflowCloud config flow."""

from homeassistant import config_entries
from homeassistant.components.weatherflow_cloud.const import DOMAIN
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_config_2(hass: HomeAssistant, mock_get_stations_combined) -> None:
    """Test the config flow (which is very simple now)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_TOKEN: "string",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_TOKEN: "string",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_api_key"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_API_TOKEN: "string",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY
