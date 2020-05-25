"""Unit tests for NetWave config-flow."""
from requests import RequestException

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.netwave.const import (
    CONF_FRAMERATE,
    CONF_HORIZONTAL_MIRROR,
    CONF_MOVE_DURATION,
    CONF_VERTICAL_MIRROR,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.data_entry_flow import RESULT_TYPE_FORM

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_show_config_form(hass):
    """Test if initial configuration form is shown."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_form_auth_failed(hass):
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.netwave.config_flow.NetwaveCameraAPI.update_info",
        side_effect=RuntimeError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: "username", CONF_PASSWORD: "password"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "auth_failed"}


async def test_form_connection_error(hass):
    """Test we handle connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.netwave.config_flow.NetwaveCameraAPI.update_info",
        side_effect=RequestException,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: "username", CONF_PASSWORD: "password"},
        )

    assert result2["type"] == "form"
    assert result2["errors"] == {"base": "connection_error"}


async def test_options_flow(hass):
    """Test config flow options."""
    conf = {
        CONF_NAME: "Camera",
        CONF_TIMEOUT: 5,
        CONF_VERTICAL_MIRROR: False,
        CONF_HORIZONTAL_MIRROR: False,
        CONF_FRAMERATE: 2,
        CONF_MOVE_DURATION: 0.5,
    }

    config_entry = MockConfigEntry(domain=DOMAIN, data=conf,)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.monoprice.async_setup_entry", return_value=True
    ):
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "config"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CONF_NAME: "Camera",
                CONF_TIMEOUT: 5,
                CONF_VERTICAL_MIRROR: False,
                CONF_HORIZONTAL_MIRROR: False,
                CONF_FRAMERATE: 2,
                CONF_MOVE_DURATION: "0.5",
            },
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {
            CONF_NAME: "Camera",
            CONF_TIMEOUT: 5,
            CONF_VERTICAL_MIRROR: False,
            CONF_HORIZONTAL_MIRROR: False,
            CONF_FRAMERATE: 2,
            CONF_MOVE_DURATION: 0.5,
        }
