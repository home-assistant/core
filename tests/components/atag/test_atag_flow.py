"""Tests for the Atag config flow."""
from unittest.mock import PropertyMock, patch

from asynctest import CoroutineMock

from homeassistant import data_entry_flow
from homeassistant.components.atag import config_flow
from homeassistant.const import CONF_DEVICE, CONF_HOST, CONF_PORT

from tests.common import MockConfigEntry

FIXTURE_USER_INPUT = {
    CONF_HOST: "127.0.0.1",
    CONF_PORT: 10000,
}
FIXTURE_COMPLETE_ENTRY = FIXTURE_USER_INPUT.copy()
FIXTURE_COMPLETE_ENTRY[CONF_DEVICE] = "device_identifier"


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.AtagConfigFlow()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_one_config_allowed(hass):
    """Test that only one Atag configuration is allowed."""
    flow = config_flow.AtagConfigFlow()
    flow.hass = hass

    MockConfigEntry(domain="atag", data=FIXTURE_USER_INPUT).add_to_hass(hass)

    step_user_result = await flow.async_step_user()

    assert step_user_result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert step_user_result["reason"] == "already_configured"

    conf = {CONF_HOST: "atag.local", CONF_PORT: 10000}

    import_config_result = await flow.async_step_import(conf)

    assert import_config_result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert import_config_result["reason"] == "already_configured"


async def test_connection_error(hass):
    """Test we show user form on Atag connection error."""

    flow = config_flow.AtagConfigFlow()
    flow.hass = hass
    result = await flow.async_step_user(user_input=FIXTURE_USER_INPUT)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "connection_error"}


async def test_full_flow_implementation(hass):
    """Test registering an integration and finishing flow works."""
    with patch(
        "homeassistant.components.atag.AtagDataStore.async_check_pair_status",
        new=CoroutineMock(),
    ), patch(
        "homeassistant.components.atag.AtagDataStore.device",
        new_callable=PropertyMock(return_value="device_identifier"),
    ):
        flow = config_flow.AtagConfigFlow()
        flow.hass = hass
        result = await flow.async_step_import(import_config=None)
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"

        result = await flow.async_step_user(user_input=FIXTURE_USER_INPUT)
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == FIXTURE_COMPLETE_ENTRY[CONF_DEVICE]
        assert result["data"] == FIXTURE_COMPLETE_ENTRY
