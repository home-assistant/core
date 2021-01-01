"""Define tests for the Bittrex config flow."""

from homeassistant import data_entry_flow, setup
from homeassistant.components.bittrex.const import CONF_API_SECRET, CONF_MARKETS, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_API_KEY

ENTRY_CONFIG = {
    CONF_API_KEY: "mock-api-key",
    CONF_API_SECRET: "mock-api-secret",
    CONF_MARKETS: ["BTC-USDT", "DGB-USDT"],
}

USER_INPUT = {
    CONF_API_KEY: "mock-api-key",
    CONF_API_SECRET: "mock-api-secret",
}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == SOURCE_USER

    await hass.config_entries.flow.async_configure(
        result["flow_id"],
    )
    await hass.async_block_till_done()
