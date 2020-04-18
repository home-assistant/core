"""Tests for the Huawei LTE config flow."""

from huawei_lte_api.enums.client import ResponseCodeEnum
from huawei_lte_api.enums.user import LoginErrorEnum, LoginStateEnum, PasswordTypeEnum
import pytest
from requests.exceptions import ConnectionError
from requests_mock import ANY

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import ssdp
from homeassistant.components.huawei_lte.const import DOMAIN
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RECIPIENT,
    CONF_URL,
    CONF_USERNAME,
)

from tests.common import MockConfigEntry

FIXTURE_USER_INPUT = {
    CONF_URL: "http://192.168.1.1/",
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "secret",
}

FIXTURE_USER_INPUT_OPTIONS = {
    CONF_NAME: DOMAIN,
    CONF_RECIPIENT: "+15555551234",
}


async def test_show_set_form(hass):
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_urlize_plain_host(hass, requests_mock):
    """Test that plain host or IP gets converted to a URL."""
    requests_mock.request(ANY, ANY, exc=ConnectionError())
    host = "192.168.100.1"
    user_input = {**FIXTURE_USER_INPUT, CONF_URL: host}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=user_input
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert user_input[CONF_URL] == f"http://{host}/"


async def test_already_configured(hass):
    """Test we reject already configured devices."""
    MockConfigEntry(
        domain=DOMAIN, data=FIXTURE_USER_INPUT, title="Already configured"
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            **FIXTURE_USER_INPUT,
            # Tweak URL a bit to check that doesn't fail duplicate detection
            CONF_URL: FIXTURE_USER_INPUT[CONF_URL].replace("http", "HTTP"),
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_connection_error(hass, requests_mock):
    """Test we show user form on connection error."""
    requests_mock.request(ANY, ANY, exc=ConnectionError())
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=FIXTURE_USER_INPUT
    )

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
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=FIXTURE_USER_INPUT
    )

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
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=FIXTURE_USER_INPUT
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_URL] == FIXTURE_USER_INPUT[CONF_URL]
    assert result["data"][CONF_USERNAME] == FIXTURE_USER_INPUT[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == FIXTURE_USER_INPUT[CONF_PASSWORD]


async def test_ssdp(hass):
    """Test SSDP discovery initiates config properly."""
    url = "http://192.168.100.1/"
    context = {"source": config_entries.SOURCE_SSDP}
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context=context,
        data={
            ssdp.ATTR_SSDP_LOCATION: "http://192.168.100.1:60957/rootDesc.xml",
            ssdp.ATTR_SSDP_ST: "upnp:rootdevice",
            ssdp.ATTR_UPNP_DEVICE_TYPE: "urn:schemas-upnp-org:device:InternetGatewayDevice:1",
            ssdp.ATTR_UPNP_FRIENDLY_NAME: "Mobile Wi-Fi",
            ssdp.ATTR_UPNP_MANUFACTURER: "Huawei",
            ssdp.ATTR_UPNP_MANUFACTURER_URL: "http://www.huawei.com/",
            ssdp.ATTR_UPNP_MODEL_NAME: "Huawei router",
            ssdp.ATTR_UPNP_MODEL_NUMBER: "12345678",
            ssdp.ATTR_UPNP_PRESENTATION_URL: url,
            ssdp.ATTR_UPNP_SERIAL: "00000000",
            ssdp.ATTR_UPNP_UDN: "uuid:XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
        },
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert context[CONF_URL] == url


async def test_options(hass):
    """Test options produce expected data."""

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=FIXTURE_USER_INPUT, options=FIXTURE_USER_INPUT_OPTIONS
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    recipient = "+15555550000"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_RECIPIENT: recipient}
    )
    assert result["data"][CONF_NAME] == DOMAIN
    assert result["data"][CONF_RECIPIENT] == [recipient]
