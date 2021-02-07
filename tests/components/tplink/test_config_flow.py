"""Define tests for the TP-Link config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.tplink.const import (
    CONF_DIMMER,
    CONF_DISCOVERY,
    CONF_LIGHT,
    CONF_RETRY_DELAY,
    CONF_RETRY_MAX_ATTEMPTS,
    CONF_STRIP,
    CONF_SWITCH,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER

from tests.common import MockConfigEntry

VALID_CONFIG = {
    CONF_LIGHT: "1.1.1.1",
    CONF_SWITCH: "1.1.1.2",
    CONF_STRIP: "1.1.1.3",
    CONF_DIMMER: "1.1.1.4",
    CONF_DISCOVERY: True,
    CONF_RETRY_DELAY: 0,
    CONF_RETRY_MAX_ATTEMPTS: 0,
}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER


async def test_create_entry(hass):
    """Test that the user step works."""
    with patch("homeassistant.components.tplink.async_setup_entry", return_value=True):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=VALID_CONFIG,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"][CONF_LIGHT] == "1.1.1.1"
        assert result["data"][CONF_SWITCH] == "1.1.1.2"
        assert result["data"][CONF_STRIP] == "1.1.1.3"
        assert result["data"][CONF_DIMMER] == "1.1.1.4"
        assert result["data"][CONF_DISCOVERY] is True
        assert result["data"][CONF_RETRY_DELAY] == 0
        assert result["data"][CONF_RETRY_MAX_ATTEMPTS] == 0


async def test_options_flow(hass):
    """Test config flow options."""
    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="123456", data=VALID_CONFIG)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    await hass.async_block_till_done()
    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()
