"""Test pi_hole config flow."""
import logging

from homeassistant.components.pi_hole.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_API_KEY
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import (
    API_KEY,
    CONF_CONFIG_FLOW,
    CONF_DATA,
    NAME,
    SWITCH_ENTITY_ID,
    _create_mocked_hole,
    _patch_config_flow_hole,
    _patch_init_hole,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry


def _flow_next(hass, flow_id):
    return next(
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == flow_id
    )


def _patch_setup():
    return patch(
        "homeassistant.components.pi_hole.async_setup_entry", return_value=True,
    )


async def test_flow_import(hass, caplog):
    """Test import flow."""
    mocked_hole = _create_mocked_hole()
    with _patch_config_flow_hole(mocked_hole), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=CONF_DATA
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == NAME
        assert result["data"] == CONF_DATA

        # duplicated server
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=CONF_DATA
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_flow_import_invalid(hass, caplog):
    """Test import flow with invalid server."""
    mocked_hole = _create_mocked_hole(True)
    with _patch_config_flow_hole(mocked_hole), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=CONF_DATA
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "cannot_connect"
        assert len([x for x in caplog.records if x.levelno == logging.ERROR]) == 1


async def test_flow_user(hass):
    """Test user initialized flow."""
    mocked_hole = _create_mocked_hole()
    with _patch_config_flow_hole(mocked_hole), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER},
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}
        _flow_next(hass, result["flow_id"])

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_CONFIG_FLOW,
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == NAME
        assert result["data"] == CONF_DATA

        # duplicated server
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_CONFIG_FLOW,
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_flow_user_invalid(hass):
    """Test user initialized flow with invalid server."""
    mocked_hole = _create_mocked_hole(True)
    with _patch_config_flow_hole(mocked_hole), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_CONFIG_FLOW
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


async def test_options_flow(hass):
    """Test config flow options."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=CONF_DATA)
    config_entry.add_to_hass(hass)

    mocked_hole = _create_mocked_hole()
    with _patch_config_flow_hole(mocked_hole), _patch_init_hole(mocked_hole):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert hass.states.get(SWITCH_ENTITY_ID) is not None
        assert config_entry.options[CONF_API_KEY] == API_KEY
        assert CONF_API_KEY not in config_entry.data

        # Remove API key
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "init"
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={}
        )
        await hass.async_block_till_done()
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {}
        assert hass.states.get(SWITCH_ENTITY_ID) is None
        assert CONF_API_KEY not in config_entry.options

        # Set new API key
        result = await hass.config_entries.options.async_init(
            config_entry.entry_id, data={CONF_API_KEY: API_KEY}
        )
        await hass.async_block_till_done()
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {CONF_API_KEY: API_KEY}
        assert hass.states.get(SWITCH_ENTITY_ID) is not None
        assert config_entry.options[CONF_API_KEY] == API_KEY
