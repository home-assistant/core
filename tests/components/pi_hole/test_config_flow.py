"""Test pi_hole config flow."""
import copy
import logging

from homeassistant.components.pi_hole.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import (
    CONF_CONFIG_FLOW,
    CONF_DATA,
    CONF_HOST,
    NAME,
    _create_mocked_hole,
    _patch_config_flow_hole,
)

from tests.async_mock import patch


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

        # duplicated name
        conf_data = copy.deepcopy(CONF_DATA)
        conf_data[CONF_HOST] = "4.3.2.1"
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf_data
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "duplicated_name"
        assert len([x for x in caplog.records if x.levelno == logging.ERROR]) == 1


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

        # duplicated name
        conf_data = copy.deepcopy(CONF_CONFIG_FLOW)
        conf_data[CONF_HOST] = "4.3.2.1"
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf_data
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "duplicated_name"


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
