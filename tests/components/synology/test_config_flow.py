"""Test synology config flow."""
from homeassistant.components.synology.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)
from homeassistant.helpers.typing import HomeAssistantType

from . import (
    CONF_ENTRY,
    CONF_FLOW,
    PASSWORD,
    TIMEOUT,
    URL,
    USERNAME,
    VERIFY_SSL,
    _patch_config_flow_device,
)

from tests.async_mock import patch
from tests.common import MockConfigEntry


def _patch_setup():
    return patch(
        "homeassistant.components.synology.async_setup_entry", return_value=True
    )


def _flow_next(hass, flow_id):
    return next(
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == flow_id
    )


async def test_flow_user(hass: HomeAssistantType):
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    _flow_next(hass, result["flow_id"])

    with _patch_config_flow_device(True) as device:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FLOW
        )
        device.assert_called_once()
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}
        _flow_next(hass, result["flow_id"])

    with _patch_config_flow_device() as device, _patch_setup():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=CONF_FLOW
        )
        device.assert_called_once_with(
            URL, USERNAME, PASSWORD, verify_ssl=VERIFY_SSL, timeout=TIMEOUT
        )
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == CONF_ENTRY


async def test_flow_import(hass: HomeAssistantType):
    """Test import flow."""
    with _patch_config_flow_device(True) as device:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=CONF_ENTRY
        )
        device.assert_called_once()
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "cannot_connect"

    with _patch_config_flow_device() as device, _patch_setup():
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=CONF_ENTRY
        )
        device.assert_called_once()
        assert result["type"] == RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == CONF_ENTRY


async def test_flow_configured(hass: HomeAssistantType):
    """Test configuring existed device."""
    MockConfigEntry(domain=DOMAIN, data=CONF_ENTRY).add_to_hass(hass)

    with _patch_config_flow_device() as device:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=CONF_FLOW
        )
        device.assert_not_called()
        assert result["type"] == RESULT_TYPE_ABORT
        assert result["reason"] == "already_configured"
