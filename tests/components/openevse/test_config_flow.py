"""Test OpenEVSE config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.openevse.const import CONF_NAME, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

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


async def test_flow_import(
    hass: HomeAssistant,
) -> None:
    """Test an import flow."""
    conf = {
        "platform": DOMAIN,
        CONF_HOST: "somefakehost.local",
        CONF_USERNAME: "fakeuser",
        CONF_PASSWORD: "fakepwd",
    }
    with patch(
        "homeassistant.components.openevse.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=conf,
        )
        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 1
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {
            CONF_NAME: "openevse",
            CONF_HOST: "somefakehost.local",
            CONF_USERNAME: "fakeuser",
            CONF_PASSWORD: "fakepwd",
        }

    with patch(
        "homeassistant.components.openevse.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=conf,
        )
        await hass.async_block_till_done()

        assert len(mock_setup_entry.mock_calls) == 0
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"
