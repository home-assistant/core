"""Test the aftership config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.aftership.config_flow import InvalidAuth
from homeassistant.components.aftership.const import DOMAIN

from tests.async_mock import patch


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.aftership.config_flow.AfterShipTest.authenticate",
        return_value=True,
    ), patch(
        "homeassistant.components.aftership.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.aftership.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "name": "My AfterShip Packages",
                "api_key": "188bdc54-30c0-407b-90fb-e6c303d7922e",
            },
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "AfterShip"
    assert result2["data"] == {
        "name": "My AfterShip Packages",
        "api_key": "188bdc54-30c0-407b-90fb-e6c303d7922e",
        "unique_id": "aftership_188bdc54",
    }
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            "name": "My AfterShip Packages",
            "api_key": "188bdc54-30c0-407b-90fb-e6c303d7922e",
        },
    )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}
