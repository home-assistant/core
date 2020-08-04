"""Test the Mullvad VPN config flow."""

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.mullvad.const import DOMAIN


async def test_form(hass):
    """Test getting the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["title"] == "Mullvad VPN"
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 0
