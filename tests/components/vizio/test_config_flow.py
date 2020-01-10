"""Tests for Vizio config flow."""
from unittest.mock import patch

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.vizio import VIZIO_SCHEMA, config_flow
from homeassistant.components.vizio.const import (
    CONF_VOLUME_STEP,
    DEFAULT_NAME,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
)
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_DEVICE_CLASS,
    CONF_HOST,
    CONF_NAME,
)

from tests.common import MockConfigEntry, mock_coro_func

NAME = "Vizio"
HOST = "192.168.1.1:9000"
DEVICE_CLASS_TV = "tv"
DEVICE_CLASS_SOUNDBAR = "soundbar"
ACCESS_TOKEN = "deadbeef"
VOLUME_STEP = 2

MOCK_VALID_TV_ENTRY = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
    CONF_ACCESS_TOKEN: ACCESS_TOKEN,
    CONF_VOLUME_STEP: VOLUME_STEP,
}

MOCK_INVALID_TV_ENTRY = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
    CONF_VOLUME_STEP: VOLUME_STEP,
}

MOCK_SOUNDBAR_ENTRY = {
    CONF_NAME: NAME,
    CONF_HOST: HOST,
    CONF_DEVICE_CLASS: DEVICE_CLASS_SOUNDBAR,
    CONF_VOLUME_STEP: VOLUME_STEP,
}


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.VizioConfigFlow()
    flow.hass = hass
    return flow


async def test_flow_works(hass):
    """Test user config."""
    flow = init_config_flow(hass)

    # test form shows
    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # test valid options
    with patch("pyvizio.VizioAsync.validate_config", side_effect=mock_coro_func(True)):
        result = await flow.async_step_user(
            {CONF_NAME: NAME, CONF_HOST: HOST, CONF_DEVICE_CLASS: DEVICE_CLASS_SOUNDBAR}
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"][CONF_NAME] == NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_DEVICE_CLASS] == DEVICE_CLASS_SOUNDBAR

    # test with all provided
    with patch("pyvizio.VizioAsync.validate_config", side_effect=mock_coro_func(True)):
        result = await flow.async_step_user(
            {
                CONF_NAME: NAME,
                CONF_HOST: HOST,
                CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
                CONF_ACCESS_TOKEN: ACCESS_TOKEN,
            }
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"][CONF_NAME] == NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_DEVICE_CLASS] == DEVICE_CLASS_TV
    assert result["data"][CONF_ACCESS_TOKEN] == ACCESS_TOKEN


async def test_options(hass):
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=CONF_NAME,
        data={
            CONF_NAME: NAME,
            CONF_HOST: HOST,
            CONF_DEVICE_CLASS: DEVICE_CLASS_TV,
            CONF_ACCESS_TOKEN: ACCESS_TOKEN,
        },
    )
    flow = init_config_flow(hass)
    options_flow = flow.async_get_options_flow(entry)

    result = await options_flow.async_step_init()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    result = await options_flow.async_step_init({CONF_VOLUME_STEP: VOLUME_STEP})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_VOLUME_STEP] == VOLUME_STEP


async def test_user_host_already_configured(hass):
    """Test host is already configured during user setup."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_SOUNDBAR_ENTRY, options={CONF_VOLUME_STEP: VOLUME_STEP}
    )
    entry.add_to_hass(hass)
    mock_entry = MOCK_SOUNDBAR_ENTRY.copy()
    mock_entry[CONF_NAME] = "newtestname"
    flow = init_config_flow(hass)
    result = await flow.async_step_user(mock_entry)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "host_exists"}


async def test_user_name_already_configured(hass):
    """Test name is already configured during user setup."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_SOUNDBAR_ENTRY, options={CONF_VOLUME_STEP: VOLUME_STEP}
    )
    entry.add_to_hass(hass)

    mock_entry = MOCK_SOUNDBAR_ENTRY.copy()
    mock_entry[CONF_HOST] = "0.0.0.0"
    flow = init_config_flow(hass)
    result = await flow.async_step_user(mock_entry)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_NAME: "name_exists"}


async def test_user_error_on_invalid_setup(hass):
    """Test with invalid_setup during user_setup."""
    flow = init_config_flow(hass)

    with patch("pyvizio.VizioAsync.validate_config", side_effect=mock_coro_func(False)):
        result = await flow.async_step_user(MOCK_VALID_TV_ENTRY)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "invalid_setup"}


async def test_user_error_on_tv_needs_token(hass):
    """Test when config fails custom validation for non null access token when device_class = tv during user setup."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user(MOCK_INVALID_TV_ENTRY)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "tv_needs_token"}


async def test_import(hass):
    """Test import step."""
    flow = init_config_flow(hass)

    # import with minimum fields only
    with patch("pyvizio.VizioAsync.validate_config", side_effect=mock_coro_func(True)):
        result = await flow.async_step_import(
            vol.Schema(VIZIO_SCHEMA)(
                {CONF_HOST: HOST, CONF_DEVICE_CLASS: DEVICE_CLASS_SOUNDBAR}
            )
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"][CONF_NAME] == DEFAULT_NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_DEVICE_CLASS] == DEVICE_CLASS_SOUNDBAR
    assert result["data"][CONF_VOLUME_STEP] == DEFAULT_VOLUME_STEP

    # import with all
    with patch("pyvizio.VizioAsync.validate_config", side_effect=mock_coro_func(True)):
        result = await flow.async_step_import(
            vol.Schema(VIZIO_SCHEMA)(MOCK_VALID_TV_ENTRY)
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"][CONF_NAME] == NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_DEVICE_CLASS] == DEVICE_CLASS_TV
    assert result["data"][CONF_ACCESS_TOKEN] == ACCESS_TOKEN
    assert result["data"][CONF_VOLUME_STEP] == VOLUME_STEP


async def test_import_entity_already_configured(hass):
    """Test entity is already configured during import setup."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_SOUNDBAR_ENTRY, options={CONF_VOLUME_STEP: VOLUME_STEP}
    )
    entry.add_to_hass(hass)
    mock_entry = MOCK_SOUNDBAR_ENTRY.copy()
    flow = init_config_flow(hass)
    result = await flow.async_step_import(mock_entry)

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_setup"


async def test_import_name_already_configured(hass):
    """Test name is already configured during user setup."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_SOUNDBAR_ENTRY, options={CONF_VOLUME_STEP: VOLUME_STEP}
    )
    entry.add_to_hass(hass)

    mock_entry = MOCK_SOUNDBAR_ENTRY.copy()
    mock_entry[CONF_HOST] = "0.0.0.0"
    flow = init_config_flow(hass)
    result = await flow.async_step_import(mock_entry)

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "name_exists"


async def test_import_host_already_configured(hass):
    """Test host is already configured during user setup."""
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_SOUNDBAR_ENTRY, options={CONF_VOLUME_STEP: VOLUME_STEP}
    )
    entry.add_to_hass(hass)

    mock_entry = MOCK_SOUNDBAR_ENTRY.copy()
    mock_entry[CONF_NAME] = "newtestname"
    flow = init_config_flow(hass)
    result = await flow.async_step_import(mock_entry)

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "host_exists"
