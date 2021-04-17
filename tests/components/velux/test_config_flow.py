"""Test the Velux config flow."""
from unittest.mock import patch

from pyvlx import PyVLXException

from homeassistant import config_entries, setup
from homeassistant.components.velux import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD

CONFIG = {DOMAIN: {CONF_HOST: "192.168.0.20", CONF_PASSWORD: "password"}}


async def test_form(hass):
    """Test we get the form."""
    return
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}


async def test_gateway_connect_exception(hass):
    """Test a error message is displayed when connection to KLF gateway fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pyvlx.PyVLX.connect",
        side_effect=PyVLXException("Login to KLF 200 failed, check credentials"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], CONFIG[DOMAIN]
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "invalid_auth"}
