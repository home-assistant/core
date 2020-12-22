"""Tests for the securitas direct config flow."""

from homeassistant import data_entry_flow
from homeassistant.components.securitas_direct import config_flow
from homeassistant.components.securitas_direct.const import (
    CONF_COUNTRY,
    CONF_INSTALLATION,
    CONF_LANG,
    DOMAIN,
    MULTI_SEC_CONFIGS,
    RELOADED,
    STEP_REAUTH,
    STEP_USER,
    UNABLE_TO_CONNECT,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_CODE, CONF_PASSWORD, CONF_USERNAME

from tests.async_mock import patch
from tests.common import MockConfigEntry


def create_config_flow(hass):
    """ Create a securitas direct config flow."""
    flow = config_flow.SecuritasConfigFlow()
    flow.hass = hass

    return flow


config = {
    CONF_USERNAME: "user1",
    CONF_PASSWORD: "password",
    CONF_INSTALLATION: "123",
    CONF_COUNTRY: "PT",
    CONF_LANG: "pt",
    CONF_CODE: 123,
}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = create_config_flow(hass)
    result = await flow.async_step_user(user_input=None)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == STEP_USER


async def test_multiple_config(hass):
    """Test multiple configurations."""
    flow = create_config_flow(hass)
    MockConfigEntry(
        domain=DOMAIN,
        data=config,
    ).add_to_hass(hass)

    step_user_result = await flow.async_step_user()
    assert step_user_result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert step_user_result["reason"] == MULTI_SEC_CONFIGS

    step_import_result = await flow.async_step_import(config)
    assert step_import_result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert step_import_result["reason"] == MULTI_SEC_CONFIGS


async def test_invalid_connection(hass):
    """Test that invalid connection."""

    flow = create_config_flow(hass)
    result = await flow.async_step_user(config)
    assert result["errors"] == {"base": UNABLE_TO_CONNECT}


async def create_entry(hass, source):
    """Create an entry and asserts result from the operation."""
    with patch("homeassistant.components.securitas_direct.config_flow.Session"), patch(
        "homeassistant.components.securitas_direct.Session"
    ), patch("homeassistant.components.securitas_direct.Installation"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": source}, data=config
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == config[CONF_INSTALLATION]
        assert result["data"] == config


async def test_create_entry(hass):
    """Test create an entry."""

    await create_entry(hass, SOURCE_USER)


async def test_import_entry(hass):
    """Test import an entry."""

    await create_entry(hass, SOURCE_IMPORT)


async def test_reauth(hass):
    """Test reauthentication."""

    MockConfigEntry(
        domain=DOMAIN,
        unique_id=config[CONF_INSTALLATION],
        data=config,
    ).add_to_hass(hass)

    with patch("homeassistant.components.securitas_direct.config_flow.Session"), patch(
        "homeassistant.components.securitas_direct.Session"
    ), patch("homeassistant.components.securitas_direct.Installation"):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH},
            data=config,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == STEP_REAUTH

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=config,
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
        assert result["reason"] == RELOADED

        assert len(hass.config_entries.async_entries()) == 1
