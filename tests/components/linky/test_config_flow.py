"""Tests for the Linky config flow."""
from unittest.mock import patch

from pylinky.exceptions import (
    PyLinkyAccessException,
    PyLinkyEnedisException,
    PyLinkyException,
    PyLinkyWrongLoginException,
)
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.linky import config_flow
from homeassistant.components.linky.const import DEFAULT_TIMEOUT, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME

from tests.common import MockConfigEntry

USERNAME = "username"
PASSWORD = "password"
TIMEOUT = 20


@pytest.fixture(name="login")
def mock_controller_login():
    """Mock a successful login."""
    with patch("pylinky.client.LinkyClient.login", return_value=True):
        yield


@pytest.fixture(name="fetch_data")
def mock_controller_fetch_data():
    """Mock a successful get data."""
    with patch("pylinky.client.LinkyClient.fetch_data", return_value={}):
        yield


@pytest.fixture(name="close_session")
def mock_controller_close_session():
    """Mock a successful closing session."""
    with patch("pylinky.client.LinkyClient.close_session", return_value=None):
        yield


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.LinkyFlowHandler()
    flow.hass = hass
    return flow


async def test_user(hass, login, fetch_data, close_session):
    """Test user config."""
    flow = init_config_flow(hass)

    result = await flow.async_step_user()
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # test with all provided
    result = await flow.async_step_user(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_TIMEOUT] == DEFAULT_TIMEOUT


async def test_import(hass, login, fetch_data, close_session):
    """Test import step."""
    flow = init_config_flow(hass)

    # import with username and password
    result = await flow.async_step_import(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_TIMEOUT] == DEFAULT_TIMEOUT

    # import with all
    result = await flow.async_step_import(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD, CONF_TIMEOUT: TIMEOUT}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_TIMEOUT] == TIMEOUT


async def test_abort_if_already_setup(hass, login, fetch_data, close_session):
    """Test we abort if Linky is already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(
        domain=DOMAIN, data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    ).add_to_hass(hass)

    # Should fail, same USERNAME (import)
    result = await flow.async_step_import(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "username_exists"

    # Should fail, same USERNAME (flow)
    result = await flow.async_step_user(
        {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_USERNAME: "username_exists"}


async def test_abort_on_login_failed(hass, close_session):
    """Test when we have errors during login."""
    flow = init_config_flow(hass)

    with patch(
        "pylinky.client.LinkyClient.login", side_effect=PyLinkyAccessException()
    ):
        result = await flow.async_step_user(
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "access"}

    with patch(
        "pylinky.client.LinkyClient.login", side_effect=PyLinkyWrongLoginException()
    ):
        result = await flow.async_step_user(
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "wrong_login"}


async def test_abort_on_fetch_failed(hass, login, close_session):
    """Test when we have errors during fetch."""
    flow = init_config_flow(hass)

    with patch(
        "pylinky.client.LinkyClient.fetch_data", side_effect=PyLinkyAccessException()
    ):
        result = await flow.async_step_user(
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "access"}

    with patch(
        "pylinky.client.LinkyClient.fetch_data", side_effect=PyLinkyEnedisException()
    ):
        result = await flow.async_step_user(
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "enedis"}

    with patch("pylinky.client.LinkyClient.fetch_data", side_effect=PyLinkyException()):
        result = await flow.async_step_user(
            {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "unknown"}
