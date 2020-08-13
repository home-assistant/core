"""Test the Omnilogic config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.omnilogic.const import DOMAIN


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    await hass.async_block_till_done()
