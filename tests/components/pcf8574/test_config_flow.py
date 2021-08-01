"""Test the PCF8574 config flow."""
from unittest.mock import patch

from homeassistant import config_entries, setup
from homeassistant.components.pcf8574.const import (
    CONF_I2C_ADDRESS,
    CONF_I2C_PORT_NUM,
    CONF_INVERT_LOGIC,
    DOMAIN,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

VALID_CONFIG = {
    CONF_I2C_PORT_NUM: 1,
    CONF_I2C_ADDRESS: 32,
    CONF_INVERT_LOGIC: True,
    CONF_NAME: "PCF8574 Test Module",
    "switch_1_name": "switch 1",
    "switch_2_name": "switch 2",
    "switch_3_name": "switch 3",
    "switch_4_name": "switch 4",
    "switch_5_name": "switch 5",
    "switch_6_name": "switch 6",
    "switch_7_name": "switch 7",
    "switch_8_name": "switch 8",
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
