"""Tests for the Cert Expiry config flow."""
import socket
import ssl
from unittest.mock import patch

from asynctest import patch as asyncpatch

from homeassistant import data_entry_flow
from homeassistant.components.cert_expiry import config_flow
from homeassistant.components.cert_expiry.const import DEFAULT_PORT
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from tests.common import MockConfigEntry

PORT = 443
HOST = "example.com"
GET_CERT_METHOD = "homeassistant.components.cert_expiry.helper.get_cert"
GET_CERT_TIME_METHOD = (
    "homeassistant.components.cert_expiry.config_flow.get_cert_time_to_expiry"
)


def init_config_flow(hass, source=SOURCE_USER):
    """Init a configuration flow."""
    flow = config_flow.CertexpiryConfigFlow()
    flow.hass = hass
    flow.context = {"source": source}
    return flow


async def test_user(hass):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # test with all provided
    with asyncpatch(GET_CERT_TIME_METHOD, return_value=1):
        result = await flow.async_step_user({CONF_HOST: HOST, CONF_PORT: PORT})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT


async def test_user_with_bad_cert(hass):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # import with certification validation error
    with patch(GET_CERT_METHOD, side_effect=ssl.SSLError("some error")):
        result = await flow.async_step_user({CONF_HOST: HOST, CONF_PORT: PORT})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT


async def test_import(hass):
    """Test import step."""
    flow = init_config_flow(hass, source=SOURCE_IMPORT)

    # import with only host
    with asyncpatch(GET_CERT_TIME_METHOD, return_value=1):
        result = await flow.async_step_import({CONF_HOST: HOST})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == DEFAULT_PORT

    # import with host and port
    with asyncpatch(GET_CERT_TIME_METHOD, return_value=1):
        result = await flow.async_step_import({CONF_HOST: HOST, CONF_PORT: PORT})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT

    # import with host and non-default port
    with asyncpatch(GET_CERT_TIME_METHOD, return_value=1):
        result = await flow.async_step_import({CONF_HOST: HOST, CONF_PORT: 888})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == f"{HOST}:888"
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == 888

    # import legacy config with name
    with asyncpatch(GET_CERT_TIME_METHOD, return_value=1):
        result = await flow.async_step_import(
            {CONF_NAME: "legacy", CONF_HOST: HOST, CONF_PORT: PORT}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == HOST
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT


async def test_bad_import(hass):
    """Test import step."""
    flow = init_config_flow(hass, source=SOURCE_IMPORT)

    with patch(GET_CERT_METHOD, side_effect=ConnectionRefusedError()):
        result = await flow.async_step_import({CONF_HOST: HOST})
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "import_failed"


async def test_abort_if_already_setup(hass):
    """Test we abort if the cert is already setup."""
    MockConfigEntry(
        domain="cert_expiry", data={CONF_PORT: DEFAULT_PORT, CONF_HOST: HOST},
    ).add_to_hass(hass)

    # Test with import source
    flow = init_config_flow(hass, source=SOURCE_IMPORT)

    # Should fail, same HOST and PORT (default)
    result = await flow.async_step_import({CONF_HOST: HOST, CONF_PORT: DEFAULT_PORT})
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "host_port_exists"

    # Test with user source
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # Should fail, same HOST and PORT (default)
    result = await flow.async_step_user({CONF_HOST: HOST, CONF_PORT: DEFAULT_PORT})
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "host_port_exists"


async def test_abort_on_socket_failed(hass):
    """Test we abort of we have errors during socket creation."""
    flow = init_config_flow(hass)

    with patch(GET_CERT_METHOD, side_effect=socket.gaierror()):
        result = await flow.async_step_user({CONF_HOST: HOST})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "resolve_failed"}

    with patch(GET_CERT_METHOD, side_effect=socket.timeout()):
        result = await flow.async_step_user({CONF_HOST: HOST})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "connection_timeout"}

    with patch(GET_CERT_METHOD, side_effect=ConnectionRefusedError):
        result = await flow.async_step_user({CONF_HOST: HOST})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "connection_refused"}
