"""Tests for the Linky config flow."""
from unittest.mock import Mock, patch

from pylinky.exceptions import (
    PyLinkyAccessException,
    PyLinkyEnedisException,
    PyLinkyException,
    PyLinkyWrongLoginException,
)
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.linky.const import DEFAULT_TIMEOUT, DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_TIMEOUT, CONF_USERNAME
from homeassistant.helpers.typing import HomeAssistantType

from tests.common import MockConfigEntry

USERNAME = "username@hotmail.fr"
USERNAME_2 = "username@free.fr"
PASSWORD = "password"
TIMEOUT = 20


@pytest.fixture(name="login")
def mock_controller_login():
    """Mock a successful login."""
    with patch(
        "homeassistant.components.linky.config_flow.LinkyClient"
    ) as service_mock:
        service_mock.return_value.login = Mock(return_value=True)
        service_mock.return_value.close_session = Mock(return_value=None)
        yield service_mock


@pytest.fixture(name="fetch_data")
def mock_controller_fetch_data():
    """Mock a successful get data."""
    with patch(
        "homeassistant.components.linky.config_flow.LinkyClient"
    ) as service_mock:
        service_mock.return_value.fetch_data = Mock(return_value={})
        service_mock.return_value.close_session = Mock(return_value=None)
        yield service_mock


async def test_user(hass: HomeAssistantType, login, fetch_data):
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=None
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    # test with all provided
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == USERNAME
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_TIMEOUT] == DEFAULT_TIMEOUT


async def test_import(hass: HomeAssistantType, login, fetch_data):
    """Test import step."""
    # import with username and password
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == USERNAME
    assert result["title"] == USERNAME
    assert result["data"][CONF_USERNAME] == USERNAME
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_TIMEOUT] == DEFAULT_TIMEOUT

    # import with all
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_USERNAME: USERNAME_2,
            CONF_PASSWORD: PASSWORD,
            CONF_TIMEOUT: TIMEOUT,
        },
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["result"].unique_id == USERNAME_2
    assert result["title"] == USERNAME_2
    assert result["data"][CONF_USERNAME] == USERNAME_2
    assert result["data"][CONF_PASSWORD] == PASSWORD
    assert result["data"][CONF_TIMEOUT] == TIMEOUT


async def test_abort_if_already_setup(hass: HomeAssistantType, login, fetch_data):
    """Test we abort if Linky is already setup."""
    MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        unique_id=USERNAME,
    ).add_to_hass(hass)

    # Should fail, same USERNAME (import)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    # Should fail, same USERNAME (flow)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_login_failed(hass: HomeAssistantType, login):
    """Test when we have errors during login."""
    login.return_value.login.side_effect = PyLinkyAccessException()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "access"}
    hass.config_entries.flow.async_abort(result["flow_id"])

    login.return_value.login.side_effect = PyLinkyWrongLoginException()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "wrong_login"}
    hass.config_entries.flow.async_abort(result["flow_id"])


async def test_fetch_failed(hass: HomeAssistantType, login):
    """Test when we have errors during fetch."""
    login.return_value.fetch_data.side_effect = PyLinkyAccessException()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "access"}
    hass.config_entries.flow.async_abort(result["flow_id"])

    login.return_value.fetch_data.side_effect = PyLinkyEnedisException()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "enedis"}
    hass.config_entries.flow.async_abort(result["flow_id"])

    login.return_value.fetch_data.side_effect = PyLinkyException()
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "unknown"}
    hass.config_entries.flow.async_abort(result["flow_id"])
