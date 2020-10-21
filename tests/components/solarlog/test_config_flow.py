"""Test the solarlog config flow."""
import pytest

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.solarlog import config_flow
from homeassistant.components.solarlog.const import DEFAULT_HOST, DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME

from tests.async_mock import patch
from tests.common import MockConfigEntry

NAME = "Solarlog test 1 2 3"
HOST = "http://1.1.1.1"


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.solarlog.config_flow.SolarLogConfigFlow._test_connection",
        return_value={"title": "solarlog test 1 2 3"},
    ), patch(
        "homeassistant.components.solarlog.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.solarlog.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"host": HOST, "name": NAME}
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "solarlog_test_1_2_3"
    assert result2["data"] == {"host": "http://1.1.1.1"}
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.fixture(name="test_connect")
def mock_controller():
    """Mock a successful _host_in_configuration_exists."""
    with patch(
        "homeassistant.components.solarlog.config_flow.SolarLogConfigFlow._test_connection",
        return_value=True,
    ):
        yield


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.SolarLogConfigFlow()
    flow.hass = hass
    return flow


async def test_user(hass, test_connect):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # tets with all provided
    result = await flow.async_step_user({CONF_NAME: NAME, CONF_HOST: HOST})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "solarlog_test_1_2_3"
    assert result["data"][CONF_HOST] == HOST


async def test_import(hass, test_connect):
    """Test import step."""
    flow = init_config_flow(hass)

    # import with only host
    result = await flow.async_step_import({CONF_HOST: HOST})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "solarlog"
    assert result["data"][CONF_HOST] == HOST

    # import with only name
    result = await flow.async_step_import({CONF_NAME: NAME})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "solarlog_test_1_2_3"
    assert result["data"][CONF_HOST] == DEFAULT_HOST

    # import with host and name
    result = await flow.async_step_import({CONF_HOST: HOST, CONF_NAME: NAME})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "solarlog_test_1_2_3"
    assert result["data"][CONF_HOST] == HOST


async def test_abort_if_already_setup(hass, test_connect):
    """Test we abort if the device is already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(
        domain="solarlog", data={CONF_NAME: NAME, CONF_HOST: HOST}
    ).add_to_hass(hass)

    # Should fail, same HOST different NAME (default)
    result = await flow.async_step_import(
        {CONF_HOST: HOST, CONF_NAME: "solarlog_test_7_8_9"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    # Should fail, same HOST and NAME
    result = await flow.async_step_user({CONF_HOST: HOST, CONF_NAME: NAME})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "already_configured"}

    # SHOULD pass, diff HOST (without http://), different NAME
    result = await flow.async_step_import(
        {CONF_HOST: "2.2.2.2", CONF_NAME: "solarlog_test_7_8_9"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "solarlog_test_7_8_9"
    assert result["data"][CONF_HOST] == "http://2.2.2.2"

    # SHOULD pass, diff HOST, same NAME
    result = await flow.async_step_import(
        {CONF_HOST: "http://2.2.2.2", CONF_NAME: NAME}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "solarlog_test_1_2_3"
    assert result["data"][CONF_HOST] == "http://2.2.2.2"
