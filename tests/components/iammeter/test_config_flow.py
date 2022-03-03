"""Test the iammeter config flow."""
from unittest.mock import Mock, patch

import pytest
from requests.exceptions import HTTPError, Timeout

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.iammeter import config_flow
from homeassistant.components.iammeter.const import DEFAULT_IP, DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_IP_ADDRESS, CONF_NAME

from tests.common import MockConfigEntry

NAME = "iammeter test 1 2 3"
HOST = "1.1.1.1"


async def test_form(hass):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.iammeter.config_flow.IammeterConfigFlow._test_connection",
        return_value={"title": "iammeter test 1 2 3"},
    ), patch(
        "homeassistant.components.iammeter.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_IP_ADDRESS: HOST, CONF_NAME: NAME}
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "iammeter_test_1_2_3"
    assert result2["data"] == {CONF_IP_ADDRESS: "1.1.1.1"}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.fixture(name="test_connect")
def mock_controller():
    """Mock a successful _host_in_configuration_exists."""
    with patch(
        "homeassistant.components.iammeter.config_flow.IammeterConfigFlow._test_connection",
        return_value=True,
    ):
        yield


@pytest.fixture(name="test_api")
def mock_controller2():
    """Mock a successful IamMeter API."""
    api = Mock()
    api.get_data.return_value = {
        "SN": "MockSN",
        "Model": "WEM3080",
        "Data": [1, 2, 3, 4, 5],
    }
    with patch("iammeter.client.Client", return_value=api):
        yield api


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.IammeterConfigFlow()
    flow.hass = hass
    return flow


async def test_user(hass, test_connect):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # tets with all provided
    result = await flow.async_step_user({CONF_NAME: NAME, CONF_IP_ADDRESS: HOST})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "iammeter_test_1_2_3"
    assert result["data"][CONF_IP_ADDRESS] == HOST


async def test_import(hass, test_connect):
    """Test import step."""
    flow = init_config_flow(hass)

    # import with only host
    result = await flow.async_step_import({CONF_IP_ADDRESS: HOST})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "iammeter"
    assert result["data"][CONF_IP_ADDRESS] == HOST

    # import with only name
    result = await flow.async_step_import({CONF_NAME: NAME})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "iammeter_test_1_2_3"
    assert result["data"][CONF_IP_ADDRESS] == DEFAULT_IP

    # import with host and name
    result = await flow.async_step_import({CONF_IP_ADDRESS: HOST, CONF_NAME: NAME})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "iammeter_test_1_2_3"
    assert result["data"][CONF_IP_ADDRESS] == HOST


async def test_abort_if_already_setup(hass, test_connect):
    """Test we abort if the device is already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(
        domain="iammeter", data={CONF_NAME: NAME, CONF_IP_ADDRESS: HOST}
    ).add_to_hass(hass)

    # Should fail, same HOST different NAME (default)
    result = await flow.async_step_import(
        {CONF_IP_ADDRESS: HOST, CONF_NAME: "iammeter_test_7_8_9"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT

    # Should fail, same HOST and NAME
    result = await flow.async_step_user({CONF_IP_ADDRESS: HOST, CONF_NAME: NAME})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_IP_ADDRESS: "already_configured"}

    # SHOULD pass, diff HOST (without http://), different NAME
    result = await flow.async_step_import(
        {CONF_IP_ADDRESS: "2.2.2.2", CONF_NAME: "iammeter_test_7_8_9"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "iammeter_test_7_8_9"
    assert result["data"][CONF_IP_ADDRESS] == "2.2.2.2"

    # SHOULD pass, diff HOST, same NAME
    result = await flow.async_step_import({CONF_IP_ADDRESS: "2.2.2.2", CONF_NAME: NAME})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "iammeter_test_1_2_3"
    assert result["data"][CONF_IP_ADDRESS] == "2.2.2.2"


async def test_connect_functions(hass, test_api):
    """Test api connect funtions."""
    # test API is ok
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_IP_ADDRESS: "3.3.3.3", CONF_NAME: "iammeter_test_10_11_12"},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    # test with ConnectionTimeout
    test_api.get_data.side_effect = Timeout
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_IP_ADDRESS: HOST, CONF_NAME: NAME},
    )

    assert result["errors"] == {CONF_IP_ADDRESS: "cannot_connect"}

    # test with HTTPError
    test_api.get_data.side_effect = HTTPError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_IP_ADDRESS: HOST, CONF_NAME: NAME},
    )

    assert result["errors"] == {CONF_IP_ADDRESS: "cannot_connect"}
