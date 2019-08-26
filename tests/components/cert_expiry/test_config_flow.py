"""Tests for the Cert Expiry config flow."""
from homeassistant import data_entry_flow
from homeassistant.components.cert_expiry import config_flow
from homeassistant.components.cert_expiry.const import DEFAULT_PORT
from homeassistant.const import CONF_PORT, CONF_NAME, CONF_HOST

from tests.common import MockConfigEntry

NAME = "Cert Expiry test 1 2 3"
PORT = 445
HOST = "google.com"


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.CertexpiryConfigFlow()
    flow.hass = hass
    return flow


async def test_user(hass):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # tets with all provided
    result = await flow.async_step_user(
        {CONF_NAME: NAME, CONF_HOST: HOST, CONF_PORT: PORT}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "cert_expiry_test_1_2_3"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT


async def test_import(hass):
    """Test import step."""
    flow = init_config_flow(hass)

    # import with only host
    result = await flow.async_step_import({CONF_HOST: HOST})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "google_com"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == DEFAULT_PORT

    # import with only host
    result = await flow.async_step_import({CONF_HOST: HOST, CONF_NAME: NAME})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "cert_expiry_test_1_2_3"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == DEFAULT_PORT

    # improt with host and port
    result = await flow.async_step_import({CONF_HOST: HOST, CONF_PORT: PORT})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "google_com"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT

    # import with all
    result = await flow.async_step_import(
        {CONF_HOST: HOST, CONF_PORT: PORT, CONF_NAME: NAME}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "cert_expiry_test_1_2_3"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT


async def test_abort_if_already_setup(hass):
    """Test we abort if the cert is already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(
        domain="cert_expiry",
        data={CONF_PORT: DEFAULT_PORT, CONF_NAME: NAME, CONF_HOST: HOST},
    ).add_to_hass(hass)

    # Should fail, same HOST and PORT (default)
    result = await flow.async_step_import(
        {CONF_HOST: HOST, CONF_NAME: NAME, CONF_PORT: DEFAULT_PORT}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "host_port_exists"

    # Should be the same HOST and PORT (default)
    result = await flow.async_step_user(
        {CONF_HOST: HOST, CONF_NAME: NAME, CONF_PORT: DEFAULT_PORT}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "host_port_exists"}

    # SHOULD pass, same Host diff PORT
    result = await flow.async_step_import(
        {CONF_HOST: HOST, CONF_NAME: NAME, CONF_PORT: 888}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "cert_expiry_test_1_2_3"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == 888
