"""Test Mikrotik setup process."""
from datetime import timedelta
from unittest.mock import patch

import librouteros
import pytest

from homeassistant import data_entry_flow
from homeassistant.components import mikrotik
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)

from tests.common import MockConfigEntry

DEMO_USER_INPUT = {
    CONF_NAME: "Home router",
    CONF_HOST: "0.0.0.0",
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_PORT: 8278,
    CONF_VERIFY_SSL: False,
}

DEMO_CONFIG = {
    CONF_NAME: "Home router",
    CONF_HOST: "0.0.0.0",
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_PORT: 8278,
    CONF_VERIFY_SSL: False,
    mikrotik.const.CONF_FORCE_DHCP: False,
    mikrotik.CONF_ARP_PING: False,
    mikrotik.CONF_DETECTION_TIME: timedelta(seconds=30),
}

DEMO_CONFIG_ENTRY = {
    CONF_NAME: "Home router",
    CONF_HOST: "0.0.0.0",
    CONF_USERNAME: "username",
    CONF_PASSWORD: "password",
    CONF_PORT: 8278,
    CONF_VERIFY_SSL: False,
    mikrotik.const.CONF_FORCE_DHCP: False,
    mikrotik.CONF_ARP_PING: False,
    mikrotik.CONF_DETECTION_TIME: 30,
}


@pytest.fixture(name="api")
def mock_mikrotik_api():
    """Mock an api."""
    with patch("librouteros.connect"):
        yield


@pytest.fixture(name="auth_error")
def mock_api_authentication_error():
    """Mock an api."""
    with patch(
        "librouteros.connect",
        side_effect=librouteros.exceptions.TrapError("invalid user name or password"),
    ):
        yield


@pytest.fixture(name="conn_error")
def mock_api_connection_error():
    """Mock an api."""
    with patch(
        "librouteros.connect", side_effect=librouteros.exceptions.ConnectionClosed
    ):
        yield


async def test_import(hass, api):
    """Test import step."""
    result = await hass.config_entries.flow.async_init(
        mikrotik.DOMAIN, context={"source": "import"}, data=DEMO_CONFIG
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Home router"
    assert result["data"][CONF_NAME] == "Home router"
    assert result["data"][CONF_HOST] == "0.0.0.0"
    assert result["data"][CONF_USERNAME] == "username"
    assert result["data"][CONF_PASSWORD] == "password"
    assert result["data"][CONF_PORT] == 8278
    assert result["data"][CONF_VERIFY_SSL] is False


async def test_flow_works(hass, api):
    """Test config flow."""

    result = await hass.config_entries.flow.async_init(
        mikrotik.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_USER_INPUT
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Home router"
    assert result["data"][CONF_NAME] == "Home router"
    assert result["data"][CONF_HOST] == "0.0.0.0"
    assert result["data"][CONF_USERNAME] == "username"
    assert result["data"][CONF_PASSWORD] == "password"
    assert result["data"][CONF_PORT] == 8278


async def test_options(hass):
    """Test updating options."""
    entry = MockConfigEntry(domain=mikrotik.DOMAIN, data=DEMO_CONFIG_ENTRY)
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "device_tracker"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            mikrotik.CONF_DETECTION_TIME: 30,
            mikrotik.CONF_ARP_PING: True,
            mikrotik.const.CONF_FORCE_DHCP: False,
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        mikrotik.CONF_DETECTION_TIME: 30,
        mikrotik.CONF_ARP_PING: True,
        mikrotik.const.CONF_FORCE_DHCP: False,
    }


async def test_host_already_configured(hass, auth_error):
    """Test host already configured."""

    entry = MockConfigEntry(domain=mikrotik.DOMAIN, data=DEMO_CONFIG_ENTRY)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        mikrotik.DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_USER_INPUT
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_name_exists(hass, api):
    """Test name already configured."""

    entry = MockConfigEntry(domain=mikrotik.DOMAIN, data=DEMO_CONFIG_ENTRY)
    entry.add_to_hass(hass)
    user_input = DEMO_USER_INPUT.copy()
    user_input[CONF_HOST] = "0.0.0.1"

    result = await hass.config_entries.flow.async_init(
        mikrotik.DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] == "form"
    assert result["errors"] == {CONF_NAME: "name_exists"}


async def test_connection_error(hass, conn_error):
    """Test error when connection is unsuccessful."""

    result = await hass.config_entries.flow.async_init(
        mikrotik.DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_USER_INPUT
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_wrong_credentials(hass, auth_error):
    """Test error when credentials are wrong."""

    result = await hass.config_entries.flow.async_init(
        mikrotik.DOMAIN, context={"source": "user"}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_USER_INPUT
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {
        CONF_USERNAME: "invalid_auth",
        CONF_PASSWORD: "invalid_auth",
    }
