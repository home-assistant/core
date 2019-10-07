"""Tests for the Huawei LTE config flow."""

from huawei_lte_api.enums.client import ResponseCodeEnum
from huawei_lte_api.enums.user import LoginErrorEnum, LoginStateEnum, PasswordTypeEnum
from requests_mock import ANY
from requests.exceptions import ConnectionError
import pytest

from homeassistant import data_entry_flow
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_URL
from homeassistant.components.huawei_lte.const import DOMAIN
from homeassistant.components.huawei_lte.config_flow import ConfigFlowHandler
from tests.common import MockConfigEntry


FIXTURE_USER_INPUT = {
    CONF_URL: "http://192.168.1.1/",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "secret",
}


async def test_show_set_form(hass):
    """Test that the setup form is served."""
    flow = ConfigFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=None)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_urlize_plain_host(hass, requests_mock):
    """Test that plain host or IP gets converted to a URL."""
    requests_mock.request(ANY, ANY, exc=ConnectionError())
    flow = ConfigFlowHandler()
    flow.hass = hass
    host = "192.168.100.1"
    user_input = {**FIXTURE_USER_INPUT, CONF_URL: host}
    result = await flow.async_step_user(user_input=user_input)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert user_input[CONF_URL] == f"http://{host}/"


async def test_already_configured(hass):
    """Test we reject already configured devices."""
    MockConfigEntry(
        domain=DOMAIN, data=FIXTURE_USER_INPUT, title="Already configured"
    ).add_to_hass(hass)

    flow = ConfigFlowHandler()
    flow.hass = hass
    # Tweak URL a bit to check that doesn't fail duplicate detection
    result = await flow.async_step_user(
        user_input={
            **FIXTURE_USER_INPUT,
            CONF_URL: FIXTURE_USER_INPUT[CONF_URL].replace("http", "HTTP"),
        }
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_connection_error(hass, requests_mock):
    """Test we show user form on connection error."""

    requests_mock.request(ANY, ANY, exc=ConnectionError())
    flow = ConfigFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=FIXTURE_USER_INPUT)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_URL: "unknown_connection_error"}


@pytest.fixture
def login_requests_mock(requests_mock):
    """Set up a requests_mock with base mocks for login tests."""
    requests_mock.request(
        ANY, FIXTURE_USER_INPUT[CONF_URL], text='<meta name="csrf_token" content="x"/>'
    )
    requests_mock.request(
        ANY,
        f"{FIXTURE_USER_INPUT[CONF_URL]}api/user/state-login",
        text=(
            f"<response><State>{LoginStateEnum.LOGGED_OUT}</State>"
            f"<password_type>{PasswordTypeEnum.SHA256}</password_type></response>"
        ),
    )
    return requests_mock


@pytest.mark.parametrize(
    ("code", "errors"),
    (
        (LoginErrorEnum.USERNAME_WRONG, {CONF_USERNAME: "incorrect_username"}),
        (LoginErrorEnum.PASSWORD_WRONG, {CONF_PASSWORD: "incorrect_password"}),
        (
            LoginErrorEnum.USERNAME_PWD_WRONG,
            {CONF_USERNAME: "incorrect_username_or_password"},
        ),
        (LoginErrorEnum.USERNAME_PWD_ORERRUN, {"base": "login_attempts_exceeded"}),
        (ResponseCodeEnum.ERROR_SYSTEM_UNKNOWN, {"base": "response_error"}),
    ),
)
async def test_login_error(hass, login_requests_mock, code, errors):
    """Test we show user form with appropriate error on response failure."""
    login_requests_mock.request(
        ANY,
        f"{FIXTURE_USER_INPUT[CONF_URL]}api/user/login",
        text=f"<error><code>{code}</code><message/></error>",
    )
    flow = ConfigFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=FIXTURE_USER_INPUT)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == errors


async def test_success(hass, login_requests_mock):
    """Test successful flow provides entry creation data."""
    login_requests_mock.request(
        ANY,
        f"{FIXTURE_USER_INPUT[CONF_URL]}api/user/login",
        text=f"<response>OK</response>",
    )
    flow = ConfigFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user(user_input=FIXTURE_USER_INPUT)

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_URL] == FIXTURE_USER_INPUT[CONF_URL]
    assert result["data"][CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]
