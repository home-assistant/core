"""Test the Coronavirus config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.coronavirus.const import DOMAIN, OPTION_WORLDWIDE


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"country": OPTION_WORLDWIDE},
    )
    assert result2["type"] == "create_entry"
    assert result2["title"] == "Worldwide"
    assert result2["result"].unique_id == OPTION_WORLDWIDE
    assert result2["data"] == {
        "country": OPTION_WORLDWIDE,
    }
    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 4
