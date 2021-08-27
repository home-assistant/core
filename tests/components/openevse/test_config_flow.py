"""Test OpenEVSE config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.openevse.const import CONF_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from tests.common import MockConfigEntry


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {
        CONF_NAME: "Testing",
        CONF_HOST: "somefakehost.local",
        CONF_USERNAME: "fakeuser",
        CONF_PASSWORD: "fakepwd",
    }

    with patch(
        "homeassistant.components.openevse.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "Testing"
        assert result["data"] == {
            CONF_NAME: "testing",
            CONF_HOST: "somefakehost.local",
            CONF_USERNAME: "fakeuser",
            CONF_PASSWORD: "fakepwd",
        }


async def test_options_flow(hass):
    """Test config flow options."""
    conf = {
        CONF_NAME: "Testing",
        CONF_HOST: "somefakehost.local",
        CONF_USERNAME: "fakeuser",
        CONF_PASSWORD: "fakepwd",
    }

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=conf[CONF_NAME],
        data=conf,
    )
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.openuv.async_setup_entry", return_value=True):
        await hass.config_entries.async_setup(config_entry.entry_id)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_USERNAME: "newfakeusername", CONF_PASSWORD: "newfakepwd"},
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options.copy() == {
            CONF_NAME: "testing",
            CONF_HOST: "somefakehost.local",
            CONF_USERNAME: "newfakeusername",
            CONF_PASSWORD: "newfakepwd",
        }
