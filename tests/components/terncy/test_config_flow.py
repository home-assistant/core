"""Test the Terncy config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.terncy.const import (
    CONF_HOST,
    CONF_IP,
    CONF_NAME,
    CONF_PORT,
    DOMAIN,
    TERNCY_HUB_SVC_NAME,
)


async def test_user_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["step_id"] == "user"

    uinput = {
        CONF_NAME: "terncy hub",
        CONF_IP: "192.168.1.100",
        CONF_PORT: 443,
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=uinput
    )
    assert result["type"] == "form"
    assert result["step_id"] == "begin_pairing"


async def test_zeroconf(hass):
    """Test zeroconf."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={
            "name": "box-12-34-56-78-0a-bc." + TERNCY_HUB_SVC_NAME,
            CONF_HOST: "192.168.1.100",
            "properties": {
                CONF_NAME: "terncy hub",
                CONF_IP: "192.168.1.100",
                CONF_PORT: 443,
            },
        },
    )
    assert result["type"] == "form"
    assert result["step_id"] == "confirm"
