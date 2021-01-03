"""Test the IamMeter config flow."""
from unittest.mock import patch

from iammeter.power_meter import IamMeterError
import pytest

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.iammeter.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from .const import HOST, NAME, PORT

from tests.common import MockConfigEntry


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.iammeter.config_flow.IammeterConfigFlow._test_connection",
        return_value={"title": "IamMeterTestDevice"},
    ), patch(
        "homeassistant.components.iammeter.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.iammeter.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": HOST, "name": NAME, "port": PORT}
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "IamMeterTestDevice"
    assert result2["data"] == {
        "host": "192.168.2.15",
        "name": "IamMeterTestDevice",
        "port": "80",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.fixture(name="test_connect")
def mock_controller():
    """Mock a successful _host_in_configuration_exists."""
    with patch(
        "homeassistant.components.iammeter.config_flow.IammeterConfigFlow._test_connection",
        return_value=True,
    ):
        yield


async def test_user(hass, test_connect):
    """Test we can start a config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # test with all provided
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_NAME: NAME, CONF_HOST: HOST, CONF_PORT: PORT},
    )
    # result = await flow.async_step_user({})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "IamMeterTestDevice"
    assert result["data"][CONF_HOST] == HOST


async def test_connect_exception(hass):
    """Test connect function."""
    with patch("iammeter.real_time_api", side_effect=IamMeterError):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_NAME: NAME, CONF_HOST: HOST, CONF_PORT: PORT},
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_NAME: "cannot_connect"}

    with patch("iammeter.real_time_api", return_value=True):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_NAME: NAME, CONF_HOST: HOST, CONF_PORT: PORT},
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_import(hass, test_connect):
    """Test import step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_HOST: HOST}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    # import with only name
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_NAME: NAME}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    # import with host and name
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: HOST, CONF_NAME: NAME},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT


async def test_abort_if_already_setup(hass, test_connect):
    """Test we abort if the device is already setup."""
    MockConfigEntry(
        domain="iammeter", data={CONF_NAME: NAME, CONF_HOST: HOST, CONF_PORT: PORT}
    ).add_to_hass(hass)

    # Should pass, same HOST different NAME (default)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: HOST, CONF_NAME: "iammeter_name", CONF_PORT: PORT},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    # Should fail, same HOST and NAME
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_NAME: NAME, CONF_PORT: PORT},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_NAME: "already_configured"}

    # SHOULD pass, diff HOST (without http://), different NAME
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "2.2.2.2", CONF_NAME: "iammeter_other_name"},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "iammeter_other_name"
    assert result["data"][CONF_HOST] == "2.2.2.2"

    # SHOULD fail, diff HOST, same NAME
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "2.2.2.2", CONF_NAME: NAME, CONF_PORT: PORT},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
