"""Define tests for the OpenUV config flow."""
from unittest.mock import patch

from regenmaschine.errors import RainMachineError

from homeassistant import data_entry_flow
from homeassistant.components.rainmachine import CONF_ZONE_RUN_TIME, DOMAIN, config_flow
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_IP_ADDRESS, CONF_PASSWORD, CONF_PORT, CONF_SSL

from tests.common import MockConfigEntry


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PASSWORD: "password",
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    MockConfigEntry(domain=DOMAIN, unique_id="192.168.1.100", data=conf).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_password(hass):
    """Test that an invalid password throws an error."""
    conf = {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PASSWORD: "bad_password",
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass
    flow.context = {"source": SOURCE_USER}

    with patch(
        "regenmaschine.client.Client.load_local",
        side_effect=RainMachineError,
    ):
        result = await flow.async_step_user(user_input=conf)
        assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}


async def test_options_flow(hass):
    """Test config flow options."""
    conf = {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PASSWORD: "password",
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="abcde12345",
        data=conf,
        options={CONF_ZONE_RUN_TIME: 900},
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.rainmachine.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_ZONE_RUN_TIME: 600}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {CONF_ZONE_RUN_TIME: 600}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass
    flow.context = {"source": SOURCE_USER}

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {
        CONF_IP_ADDRESS: "192.168.1.100",
        CONF_PASSWORD: "password",
        CONF_PORT: 8080,
        CONF_SSL: True,
    }

    flow = config_flow.RainMachineFlowHandler()
    flow.hass = hass
    flow.context = {"source": SOURCE_USER}

    with patch(
        "regenmaschine.client.Client.load_local",
        return_value=True,
    ):
        result = await flow.async_step_user(user_input=conf)

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "192.168.1.100"
        assert result["data"] == {
            CONF_IP_ADDRESS: "192.168.1.100",
            CONF_PASSWORD: "password",
            CONF_PORT: 8080,
            CONF_SSL: True,
            CONF_ZONE_RUN_TIME: 600,
        }
