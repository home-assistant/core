"""Test the Qbittorrent Flow."""

from qbittorrent.client import LoginRequired
from requests.exceptions import RequestException

from homeassistant import data_entry_flow
from homeassistant.components.qbittorrent.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.data_entry_flow import RESULT_TYPE_FORM

from tests.async_mock import MagicMock, patch


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == SOURCE_USER


async def test_invalid_server(hass):
    """Test handle invalid credentials."""
    mocked_client = _create_mocked_client(True, False)
    with patch(
        "homeassistant.components.qbittorrent.client.Client",
        return_value=mocked_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

        _flow_next(hass, result["flow_id"])
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_URL: "http://testurl.org",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_invalid_credentials(hass):
    """Test handle invalid credentials."""
    mocked_client = _create_mocked_client(False, True)
    with patch(
        "homeassistant.components.qbittorrent.client.Client",
        return_value=mocked_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {}

        _flow_next(hass, result["flow_id"])
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_URL: "http://testurl.org",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        assert result["type"] == RESULT_TYPE_FORM
        assert result["errors"] == {"base": "invalid_auth"}


def _create_mocked_client(raise_request_exception=False, raise_login_exception=False):
    mocked_client = MagicMock()
    if raise_request_exception:
        mocked_client.login.side_effect = RequestException("Mocked Exception")
    if raise_login_exception:
        mocked_client.login.side_effect = LoginRequired()
    return mocked_client


def _flow_next(hass, flow_id):
    return next(
        flow
        for flow in hass.config_entries.flow.async_progress()
        if flow["flow_id"] == flow_id
    )
