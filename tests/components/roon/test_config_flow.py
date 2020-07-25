"""Test the roon config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.roon.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.roon.const import DOMAIN

from tests.async_mock import patch


async def test_form_and_auth(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.roon.config_flow.RoonHub.authenticate",
        return_value="good_token",
    ), patch(
        "homeassistant.components.roon.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.roon.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.1.1.1"}
        )
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Roon Labs Music Player"
    assert result2["data"] == {"host": "1.1.1.1", "api_key": "good_token"}
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.roon.config_flow.RoonHub.authenticate",
        side_effect=InvalidAuth,
    ):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.1.1.1"}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass):
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.roon.config_flow.RoonHub.authenticate",
        side_effect=CannotConnect,
    ):
        await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": "1.1.1.1"}
        )

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "cannot_connect"}
