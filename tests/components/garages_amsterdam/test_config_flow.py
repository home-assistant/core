"""Test the Garages Amsterdam config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.garages_amsterdam.const import DOMAIN


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {"garage_name": "IJDok"},
    )
    assert result2["type"] == "create_entry"
    assert result2["title"] == "IJDok"
    assert result2["result"].unique_id == "IJDok"
    assert result2["data"] == {
        "garage_name": "IJDok",
    }

    await hass.async_block_till_done()
    assert len(hass.states.async_all()) == 5
