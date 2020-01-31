"""Tests for the Cert Expiry config flow."""
import socket
import ssl
from unittest.mock import patch

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.cert_expiry import config_flow
from homeassistant.components.cert_expiry.const import DEFAULT_NAME, DEFAULT_PORT
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT

from tests.common import MockConfigEntry, mock_coro

NAME = "Cert Expiry test 1 2 3"
PORT = 443
HOST = "example.com"


@pytest.fixture(name="test_connect")
def mock_controller():
    """Mock a successful _prt_in_configuration_exists."""
    with patch(
        "homeassistant.components.cert_expiry.config_flow.CertexpiryConfigFlow._test_connection",
        side_effect=lambda *_: mock_coro(True),
    ):
        yield


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.CertexpiryConfigFlow()
    flow.hass = hass
    return flow


async def test_user(hass, test_connect):
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
    assert result["title"] == NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT


async def test_import(hass, test_connect):
    """Test import step."""
    flow = init_config_flow(hass)

    # import with only host
    result = await flow.async_step_import({CONF_HOST: HOST})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == DEFAULT_PORT

    # import with host and name
    result = await flow.async_step_import({CONF_HOST: HOST, CONF_NAME: NAME})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == DEFAULT_PORT

    # improt with host and port
    result = await flow.async_step_import({CONF_HOST: HOST, CONF_PORT: PORT})
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT

    # import with all
    result = await flow.async_step_import(
        {CONF_HOST: HOST, CONF_PORT: PORT, CONF_NAME: NAME}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == PORT


async def test_abort_if_already_setup(hass, test_connect):
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
    assert result["title"] == NAME
    assert result["data"][CONF_HOST] == HOST
    assert result["data"][CONF_PORT] == 888


async def test_abort_on_socket_failed(hass):
    """Test we abort of we have errors during socket creation."""
    flow = init_config_flow(hass)

    with patch("socket.create_connection", side_effect=socket.gaierror()):
        result = await flow.async_step_user({CONF_HOST: HOST})
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {CONF_HOST: "resolve_failed"}

    with patch("socket.create_connection", side_effect=socket.timeout()):
        result = await flow.async_step_user({CONF_HOST: HOST})
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {CONF_HOST: "connection_timeout"}

    with patch(
        "socket.create_connection",
        side_effect=ssl.CertificateError(f"{HOST} doesn't match somethingelse.com"),
    ):
        result = await flow.async_step_user({CONF_HOST: HOST})
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {CONF_HOST: "wrong_host"}

    with patch(
        "socket.create_connection", side_effect=ssl.CertificateError("different error")
    ):
        result = await flow.async_step_user({CONF_HOST: HOST})
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {CONF_HOST: "certificate_error"}

    with patch("socket.create_connection", side_effect=ssl.SSLError()):
        result = await flow.async_step_user({CONF_HOST: HOST})
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {CONF_HOST: "certificate_error"}
