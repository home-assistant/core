"""Define tests for the Luftdaten config flow."""
from datetime import timedelta

from homeassistant import data_entry_flow
from homeassistant.components.luftdaten import DOMAIN, config_flow
from homeassistant.components.luftdaten.const import CONF_SENSOR_ID
from homeassistant.const import CONF_SCAN_INTERVAL, CONF_SHOW_ON_MAP

from tests.async_mock import patch
from tests.common import MockConfigEntry


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {CONF_SENSOR_ID: "12345abcde"}

    MockConfigEntry(domain=DOMAIN, data=conf).add_to_hass(hass)
    flow = config_flow.LuftDatenFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=conf)
    assert result["errors"] == {CONF_SENSOR_ID: "sensor_exists"}


async def test_communication_error(hass):
    """Test that no sensor is added while unable to communicate with API."""
    conf = {CONF_SENSOR_ID: "12345abcde"}

    flow = config_flow.LuftDatenFlowHandler()
    flow.hass = hass

    with patch("luftdaten.Luftdaten.get_data", return_value=None):
        result = await flow.async_step_user(user_input=conf)
        assert result["errors"] == {CONF_SENSOR_ID: "invalid_sensor"}


async def test_invalid_sensor(hass):
    """Test that an invalid sensor throws an error."""
    conf = {CONF_SENSOR_ID: "12345abcde"}

    flow = config_flow.LuftDatenFlowHandler()
    flow.hass = hass

    with patch("luftdaten.Luftdaten.get_data", return_value=False), patch(
        "luftdaten.Luftdaten.validate_sensor", return_value=False
    ):
        result = await flow.async_step_user(user_input=conf)
        assert result["errors"] == {CONF_SENSOR_ID: "invalid_sensor"}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    flow = config_flow.LuftDatenFlowHandler()
    flow.hass = hass

    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_import(hass):
    """Test that the import step works."""
    conf = {CONF_SENSOR_ID: "12345abcde", CONF_SHOW_ON_MAP: False}

    flow = config_flow.LuftDatenFlowHandler()
    flow.hass = hass

    with patch("luftdaten.Luftdaten.get_data", return_value=True), patch(
        "luftdaten.Luftdaten.validate_sensor", return_value=True
    ):
        result = await flow.async_step_import(import_config=conf)

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "12345abcde"
        assert result["data"] == {
            CONF_SENSOR_ID: "12345abcde",
            CONF_SHOW_ON_MAP: False,
            CONF_SCAN_INTERVAL: 600,
        }


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {
        CONF_SENSOR_ID: "12345abcde",
        CONF_SHOW_ON_MAP: False,
        CONF_SCAN_INTERVAL: timedelta(minutes=5),
    }

    flow = config_flow.LuftDatenFlowHandler()
    flow.hass = hass

    with patch("luftdaten.Luftdaten.get_data", return_value=True), patch(
        "luftdaten.Luftdaten.validate_sensor", return_value=True
    ):
        result = await flow.async_step_user(user_input=conf)

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "12345abcde"
        assert result["data"] == {
            CONF_SENSOR_ID: "12345abcde",
            CONF_SHOW_ON_MAP: False,
            CONF_SCAN_INTERVAL: 300,
        }
