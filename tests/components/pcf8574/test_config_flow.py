"""Test the PCF8574 config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.pcf8574.const import (
    CONF_I2C_ADDRESS,
    CONF_I2C_PORT_NUM,
    CONF_INPUT,
    CONF_INVERT_LOGIC,
    DOMAIN,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

VALID_CONFIG = {
    CONF_I2C_PORT_NUM: 1,
    CONF_I2C_ADDRESS: 32,
    CONF_NAME: "PCF8574 Test Module",
}


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}


async def test_ioerror(hass: HomeAssistant) -> None:
    """Test IO Error when device is not accessible."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=VALID_CONFIG
    )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "ioerror"}


async def test_create_integration(hass: HomeAssistant) -> None:
    """Test Create PCF8574 Integration."""
    with patch("homeassistant.components.pcf8574.config_flow.PCF8574", autospec=True):
        await setup.async_setup_component(hass, "persistent_notification", {})
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=VALID_CONFIG
        )

    assert result["type"] == "form"
    assert result["errors"] == {}
    # add first pin, switch, default
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"add_another": True}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}
    # add second pin, switch, invert logic
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"add_another": True, CONF_INVERT_LOGIC: True}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}
    # add third pin, binay_sensor
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={"add_another": False, CONF_INPUT: True}
    )
    assert result["type"] == "create_entry"


async def test_unexpected_exception(hass: HomeAssistant) -> None:
    """Test Create PCF8574 Integration."""
    with patch(
        "homeassistant.components.pcf8574.config_flow.PCF8574",
        side_effect=NotImplementedError,
    ):
        await setup.async_setup_component(hass, "persistent_notification", {})
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=VALID_CONFIG
        )
    assert result["type"] == "form"
    assert result["errors"] == {"base": "unknown"}
