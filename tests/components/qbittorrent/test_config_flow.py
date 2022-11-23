"""Test the qBittorrent config flow."""
from unittest.mock import patch

import pytest
from requests.exceptions import RequestException
from requests.sessions import Session

from homeassistant.components.qbittorrent.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SOURCE,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

CONFIG_VALID = {
    CONF_NAME: "abcd",
    CONF_URL: "http://localhost:8080",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_VERIFY_SSL: True,
}


CONFIG_INVALID_AUTH = {
    CONF_NAME: "abcd",
    CONF_URL: "http://localhost:8080",
    CONF_USERNAME: "null",
    CONF_PASSWORD: "none",
    CONF_VERIFY_SSL: True,
}


CONFIG_CANNOT_CONNECT = {
    CONF_NAME: "abcd",
    CONF_URL: "http://nowhere:23456",
    CONF_USERNAME: "user",
    CONF_PASSWORD: "pass",
    CONF_VERIFY_SSL: True,
}


@pytest.fixture(name="api")
def mock_qbittorrent_api():
    """Mock an api."""
    with patch.object(Session, "get"), patch.object(Session, "post"):
        yield


@pytest.fixture(name="ok")
def mock_api_login_ok():
    """Mock successful login."""

    class OkResponse:
        """Mock an OK response for login."""

        text: str = "Ok."

    with patch.object(Session, "post", return_value=OkResponse()):
        yield


@pytest.fixture(name="invalid_auth")
def mock_api_invalid_auth():
    """Mock invalid credential."""

    class InvalidAuthResponse:
        """Mock an invalid auth response."""

        text: str = "Wrong username/password"

    with patch.object(Session, "post", return_value=InvalidAuthResponse()):
        yield


@pytest.fixture(name="cannot_connect")
def mock_api_cannot_connect():
    """Mock connection failure."""
    with patch.object(Session, "get", side_effect=RequestException()):
        yield


@pytest.fixture(name="qbittorrent_setup", autouse=True)
def qbittorrent_setup_fixture():
    """Mock qbittorrent entry setup."""
    with patch(
        "homeassistant.components.qbittorrent.async_setup_entry", return_value=True
    ):
        yield


async def test_show_form_no_input(hass: HomeAssistant):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER


async def test_flow_user(hass: HomeAssistant, api, ok):
    """Test user initialized flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=CONFIG_VALID,
    )
    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == CONFIG_VALID[CONF_NAME]
    assert result["data"] == CONFIG_VALID


async def test_invalid_auth(hass: HomeAssistant, api, invalid_auth):
    """Test user initialized flow with invalid credential."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=CONFIG_INVALID_AUTH,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert result["errors"] == {"base": "invalid_auth"}


async def test_cannot_connect(hass: HomeAssistant, api, cannot_connect):
    """Test user initialized flow with connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
        data=CONFIG_INVALID_AUTH,
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == SOURCE_USER
    assert result["errors"] == {"base": "cannot_connect"}


async def test_flow_user_already_configured(hass: HomeAssistant, api):
    """Test user initialized flow with duplicate server."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=CONFIG_VALID,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data=CONFIG_VALID
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
