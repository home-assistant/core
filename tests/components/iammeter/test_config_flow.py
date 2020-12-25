"""Test the IamMeter config flow."""
import pytest

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components import ssdp
from homeassistant.components.iammeter import config_flow
from homeassistant.components.iammeter.const import DEFAULT_HOST, DOMAIN
from homeassistant.components.ssdp import ATTR_SSDP_LOCATION
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.exceptions import PlatformNotReady

from tests.async_mock import patch
from tests.common import MockConfigEntry

NAME = "IamMeterTestDevice"
HOST = "192.168.2.15"
PORT = "80"


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


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.IammeterConfigFlow()
    flow.hass = hass
    return flow


async def test_connection_error(hass):
    """Test connection timeout."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    flow = init_config_flow(hass)
    # test with all provided
    await flow.async_step_user(
        user_input={CONF_NAME: NAME, CONF_HOST: HOST, CONF_PORT: PORT}
    )
    with pytest.raises(PlatformNotReady):
        print("PlatformNotReady")


async def test_user(hass):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # test with all provided
    result = await flow.async_step_user({CONF_NAME: NAME, CONF_HOST: HOST})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "IamMeterTestDevice"
    assert result["data"][CONF_HOST] == HOST


async def test_ssdp(hass):
    """Test ssdp."""
    flow = init_config_flow(hass)
    discovery_info = {}
    discovery_info[ssdp.ATTR_UPNP_FRIENDLY_NAME] = "iamMeter-ASDFASDF"
    discovery_info[ATTR_SSDP_LOCATION] = "http://192.168.2.15/info.xml"
    flow.context = {}
    result = await flow.async_step_ssdp(discovery_info=discovery_info)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_import(hass):
    """Test import step."""
    flow = init_config_flow(hass)

    # import with only host
    result = await flow.async_step_import({CONF_HOST: HOST})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "IamMeter"
    assert result["data"][CONF_HOST] == HOST

    # import with only name
    result = await flow.async_step_import({CONF_NAME: NAME})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "IamMeterTestDevice"
    assert result["data"][CONF_HOST] == DEFAULT_HOST

    # import with host and name
    result = await flow.async_step_import({CONF_HOST: HOST, CONF_NAME: NAME})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "IamMeterTestDevice"
    assert result["data"][CONF_HOST] == HOST


async def test_abort_if_already_setup(hass):
    """Test we abort if the device is already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(
        domain="iammeter", data={CONF_NAME: NAME, CONF_HOST: HOST, CONF_PORT: PORT}
    ).add_to_hass(hass)

    # Should pass, same HOST different NAME (default)
    result = await flow.async_step_import(
        {CONF_HOST: HOST, CONF_NAME: "iammeter_other_name", CONF_PORT: PORT}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY

    # Should fail, same HOST and NAME
    result = await flow.async_step_user(
        {CONF_HOST: HOST, CONF_NAME: NAME, CONF_PORT: PORT}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_NAME: "already_configured"}

    # SHOULD pass, diff HOST (without http://), different NAME
    result = await flow.async_step_import(
        {CONF_HOST: "2.2.2.2", CONF_NAME: "iammeter_other_name"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "iammeter_other_name"
    assert result["data"][CONF_HOST] == "2.2.2.2"

    # SHOULD fail, diff HOST, same NAME
    result = await flow.async_step_import(
        {CONF_HOST: "2.2.2.2", CONF_NAME: NAME, CONF_PORT: PORT}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"
