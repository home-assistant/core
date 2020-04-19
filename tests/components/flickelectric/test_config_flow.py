"""Test the Flick Electric config flow."""
from asynctest import patch

from homeassistant import config_entries, setup
from homeassistant.components.flickelectric.const import DOMAIN


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.flickelectric.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.flickelectric.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username", "password": "test-password"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Flick Electric"
    assert result2["data"] == {
        "username": "test-username",
        "password": "test-password",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
