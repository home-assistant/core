"""Test the WeatherflowCloud config flow."""
from unittest.mock import AsyncMock

from homeassistant import config_entries
from homeassistant.components.weatherflow_cloud.const import CONF_STATION_ID, DOMAIN
from homeassistant.const import CONF_API_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form_with_errors(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_validate_and_get_station_info_side_effects: AsyncMock,
) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STATION_ID: 1234,
            CONF_API_TOKEN: "string",
        },
    )
    await hass.async_block_till_done()
    assert result["errors"] == {"base": "wrong_station_id"}
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STATION_ID: 1234,
            CONF_API_TOKEN: "string",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "bad_request"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STATION_ID: 1234,
            CONF_API_TOKEN: "string",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "server_error"}
    assert result["type"] == FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STATION_ID: 1234,
            CONF_API_TOKEN: "string",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "wrong_token"}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_STATION_ID: 1234,
            CONF_API_TOKEN: "string",
        },
    )
    await hass.async_block_till_done()
    assert result["type"] == FlowResultType.CREATE_ENTRY

    # Validate entry is what we expect it to be
