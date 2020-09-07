"""Test Goal Zero Yeti config flow."""
import logging

from homeassistant.components.goalzero.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import (
    CONF_CONFIG_FLOW,
    CONF_DATA,
    FAKE_HOST,
    NAME,
    _create_mocked_yeti,
    _patch_config_flow_yeti,
)

from tests.async_mock import patch

_LOGGER = logging.getLogger(__name__)


def _flow_next(hass, flow_id):
    return next(
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == flow_id
    )


def _patch_setup():
    return patch(
        "homeassistant.components.goalzero.async_setup_entry",
        return_value=True,
    )


async def test_flow_user(hass):
    """Test user initialized flow."""
    mocked_yeti = await _create_mocked_yeti()
    with _patch_config_flow_yeti(mocked_yeti), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}
        _flow_next(hass, result["flow_id"])

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=CONF_CONFIG_FLOW,
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == NAME
        assert result["data"] == CONF_DATA

        # duplicated server
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data=CONF_CONFIG_FLOW,
        )
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"


async def test_flow_user_invalid(hass):
    """Test user initialized flow with invalid server."""
    mocked_yeti = await _create_mocked_yeti(True)
    with _patch_config_flow_yeti(mocked_yeti), _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_CONFIG_FLOW
        )
        _LOGGER.error(result)
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["flow_id"] is not None
        assert result["data"] != {"host": None}
        assert result["data"] != {"host": FAKE_HOST}
