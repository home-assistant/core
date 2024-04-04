"""Tests for the Huawei LTE config flow."""

from typing import Any
from unittest.mock import patch
from urllib.parse import urlparse, urlunparse

from huawei_lte_api.enums.client import ResponseCodeEnum
from huawei_lte_api.enums.user import LoginErrorEnum, LoginStateEnum, PasswordTypeEnum
import pytest
import requests.exceptions
from requests.exceptions import ConnectionError
import requests_mock
from requests_mock import ANY

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.components.huawei_lte.const import CONF_UNAUTHENTICATED_MODE, DOMAIN
from homeassistant.const import (
    CONF_NAME,
    CONF_PASSWORD,
    CONF_RECIPIENT,
    CONF_URL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

FIXTURE_UNIQUE_ID = "SERIALNUMBER"

FIXTURE_USER_INPUT: dict[str, Any] = {
    CONF_URL: "http://192.168.1.1/",
    CONF_VERIFY_SSL: False,
    CONF_USERNAME: "admin",
    CONF_PASSWORD: "secret",
}

FIXTURE_USER_INPUT_OPTIONS = {
    CONF_NAME: DOMAIN,
    CONF_RECIPIENT: "+15555551234",
}


async def test_show_set_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=None
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_urlize_plain_host(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker
) -> None:
    """Test that plain host or IP gets converted to a URL."""
    requests_mock.request(ANY, ANY, exc=ConnectionError())
    host = "192.168.100.1"
    user_input = {**FIXTURE_USER_INPUT, CONF_URL: host}
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert user_input[CONF_URL] == f"http://{host}/"


async def test_already_configured(
    hass: HomeAssistant, requests_mock: requests_mock.Mocker, login_requests_mock
) -> None:
    """Test we reject already configured devices."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_UNIQUE_ID,
        data=FIXTURE_USER_INPUT,
        title="Already configured",
    ).add_to_hass(hass)

    login_requests_mock.request(
        ANY,
        f"{FIXTURE_USER_INPUT[CONF_URL]}api/user/login",
        text="<response>OK</response>",
    )
    requests_mock.request(
        ANY,
        f"{FIXTURE_USER_INPUT[CONF_URL]}api/device/information",
        text=f"<response><SerialNumber>{FIXTURE_UNIQUE_ID}</SerialNumber></response>",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=FIXTURE_USER_INPUT,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("exception", "errors", "data_patch"),
    [
        (ConnectionError(), {CONF_URL: "unknown"}, {}),
        (requests.exceptions.SSLError(), {CONF_URL: "ssl_error_try_plain"}, {}),
        (
            requests.exceptions.SSLError(),
            {CONF_URL: "ssl_error_try_unverified"},
            {CONF_VERIFY_SSL: True},
        ),
    ],
)
async def test_connection_errors(
    hass: HomeAssistant,
    requests_mock: requests_mock.Mocker,
    exception: Exception,
    errors: dict[str, str],
    data_patch: dict[str, Any],
):
    """Test we show user form on various errors."""
    requests_mock.request(ANY, ANY, exc=exception)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=FIXTURE_USER_INPUT | data_patch,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == errors


@pytest.fixture
def login_requests_mock(requests_mock):
    """Set up a requests_mock with base mocks for login tests."""
    https_url = urlunparse(
        urlparse(FIXTURE_USER_INPUT[CONF_URL])._replace(scheme="https")
    )
    for url in FIXTURE_USER_INPUT[CONF_URL], https_url:
        requests_mock.request(ANY, url, text='<meta name="csrf_token" content="x"/>')
        requests_mock.request(
            ANY,
            f"{url}api/user/state-login",
            text=(
                f"<response><State>{LoginStateEnum.LOGGED_OUT}</State>"
                f"<password_type>{PasswordTypeEnum.SHA256}</password_type></response>"
            ),
        )
        requests_mock.request(
            ANY,
            f"{url}api/user/logout",
            text="<response>OK</response>",
        )
    return requests_mock


@pytest.mark.parametrize(
    ("request_outcome", "fixture_override", "errors"),
    [
        (
            {
                "text": f"<error><code>{LoginErrorEnum.USERNAME_WRONG}</code><message/></error>",
            },
            {},
            {CONF_USERNAME: "incorrect_username"},
        ),
        (
            {
                "text": f"<error><code>{LoginErrorEnum.PASSWORD_WRONG}</code><message/></error>",
            },
            {},
            {CONF_PASSWORD: "incorrect_password"},
        ),
        (
            {
                "text": f"<error><code>{LoginErrorEnum.USERNAME_PWD_WRONG}</code><message/></error>",
            },
            {},
            {CONF_USERNAME: "invalid_auth"},
        ),
        (
            {
                "text": f"<error><code>{LoginErrorEnum.USERNAME_PWD_OVERRUN}</code><message/></error>",
            },
            {},
            {"base": "login_attempts_exceeded"},
        ),
        (
            {
                "text": f"<error><code>{ResponseCodeEnum.ERROR_SYSTEM_UNKNOWN}</code><message/></error>",
            },
            {},
            {"base": "response_error"},
        ),
        ({}, {CONF_URL: "/foo/bar"}, {CONF_URL: "invalid_url"}),
        (
            {
                "exc": requests.exceptions.Timeout,
            },
            {},
            {CONF_URL: "connection_timeout"},
        ),
    ],
)
async def test_login_error(
    hass: HomeAssistant, login_requests_mock, request_outcome, fixture_override, errors
) -> None:
    """Test we show user form with appropriate error on response failure."""
    login_requests_mock.request(
        ANY,
        f"{FIXTURE_USER_INPUT[CONF_URL]}api/user/login",
        **request_outcome,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={**FIXTURE_USER_INPUT, **fixture_override},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == errors


@pytest.mark.parametrize("scheme", ["http", "https"])
async def test_success(hass: HomeAssistant, login_requests_mock, scheme: str) -> None:
    """Test successful flow provides entry creation data."""
    user_input = {
        **FIXTURE_USER_INPUT,
        CONF_URL: urlunparse(
            urlparse(FIXTURE_USER_INPUT[CONF_URL])._replace(scheme=scheme)
        ),
    }

    login_requests_mock.request(
        ANY,
        f"{user_input[CONF_URL]}api/user/login",
        text="<response>OK</response>",
    )
    with (
        patch("homeassistant.components.huawei_lte.async_setup"),
        patch("homeassistant.components.huawei_lte.async_setup_entry"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=user_input,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_URL] == user_input[CONF_URL]
    assert result["data"][CONF_USERNAME] == user_input[CONF_USERNAME]
    assert result["data"][CONF_PASSWORD] == user_input[CONF_PASSWORD]


@pytest.mark.parametrize(
    ("requests_mock_request_kwargs", "upnp_data", "expected_result"),
    [
        (
            {
                "method": ANY,
                "url": f"{FIXTURE_USER_INPUT[CONF_URL]}api/device/basic_information",
                "text": "<response><devicename>Mock device</devicename></response>",
            },
            {
                ssdp.ATTR_UPNP_FRIENDLY_NAME: "Mobile Wi-Fi",
                ssdp.ATTR_UPNP_SERIAL: "00000000",
            },
            {
                "type": FlowResultType.FORM,
                "step_id": "user",
                "errors": {},
            },
        ),
        (
            {
                "method": ANY,
                "url": f"{FIXTURE_USER_INPUT[CONF_URL]}api/device/basic_information",
                "text": "<error><code>100002</code><message/></error>",
            },
            {
                ssdp.ATTR_UPNP_FRIENDLY_NAME: "Mobile Wi-Fi",
                # No ssdp.ATTR_UPNP_SERIAL
            },
            {
                "type": FlowResultType.FORM,
                "step_id": "user",
                "errors": {},
            },
        ),
        (
            {
                "method": ANY,
                "url": f"{FIXTURE_USER_INPUT[CONF_URL]}api/device/basic_information",
                "exc": Exception("Something unexpected"),
            },
            {
                # Does not matter
            },
            {
                "type": FlowResultType.ABORT,
                "reason": "unsupported_device",
            },
        ),
    ],
)
async def test_ssdp(
    hass: HomeAssistant,
    login_requests_mock,
    requests_mock_request_kwargs,
    upnp_data,
    expected_result,
) -> None:
    """Test SSDP discovery initiates config properly."""
    url = FIXTURE_USER_INPUT[CONF_URL][:-1]  # strip trailing slash for appending port
    context = {"source": config_entries.SOURCE_SSDP}
    login_requests_mock.request(**requests_mock_request_kwargs)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context=context,
        data=ssdp.SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="upnp:rootdevice",
            ssdp_location=f"{url}:60957/rootDesc.xml",
            upnp={
                ssdp.ATTR_UPNP_DEVICE_TYPE: "urn:schemas-upnp-org:device:InternetGatewayDevice:1",
                ssdp.ATTR_UPNP_MANUFACTURER: "Huawei",
                ssdp.ATTR_UPNP_MANUFACTURER_URL: "http://www.huawei.com/",
                ssdp.ATTR_UPNP_MODEL_NAME: "Huawei router",
                ssdp.ATTR_UPNP_MODEL_NUMBER: "12345678",
                ssdp.ATTR_UPNP_PRESENTATION_URL: url,
                ssdp.ATTR_UPNP_UDN: "uuid:XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX",
                **upnp_data,
            },
        ),
    )

    for k, v in expected_result.items():
        assert result[k] == v  # type: ignore[literal-required] # expected is a subset
    if result.get("data_schema"):
        assert result["data_schema"] is not None
        assert result["data_schema"]({})[CONF_URL] == url + "/"


@pytest.mark.parametrize(
    ("login_response_text", "expected_result", "expected_entry_data"),
    [
        (
            "<response>OK</response>",
            {
                "type": FlowResultType.ABORT,
                "reason": "reauth_successful",
            },
            FIXTURE_USER_INPUT,
        ),
        (
            f"<error><code>{LoginErrorEnum.PASSWORD_WRONG}</code><message/></error>",
            {
                "type": FlowResultType.FORM,
                "errors": {CONF_PASSWORD: "incorrect_password"},
                "step_id": "reauth_confirm",
            },
            {**FIXTURE_USER_INPUT, CONF_PASSWORD: "invalid-password"},
        ),
    ],
)
async def test_reauth(
    hass: HomeAssistant,
    login_requests_mock,
    login_response_text,
    expected_result,
    expected_entry_data,
) -> None:
    """Test reauth."""
    mock_entry_data = {**FIXTURE_USER_INPUT, CONF_PASSWORD: "invalid-password"}
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=FIXTURE_UNIQUE_ID,
        data=mock_entry_data,
        title="Reauth canary",
    )
    entry.add_to_hass(hass)

    context = {
        "source": config_entries.SOURCE_REAUTH,
        "unique_id": entry.unique_id,
        "entry_id": entry.entry_id,
    }
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context=context, data=entry.data
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["data_schema"] is not None
    assert result["data_schema"]({}) == {
        CONF_USERNAME: mock_entry_data[CONF_USERNAME],
        CONF_PASSWORD: mock_entry_data[CONF_PASSWORD],
    }
    assert not result["errors"]

    login_requests_mock.request(
        ANY,
        f"{FIXTURE_USER_INPUT[CONF_URL]}api/user/login",
        text=login_response_text,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: FIXTURE_USER_INPUT[CONF_USERNAME],
            CONF_PASSWORD: FIXTURE_USER_INPUT[CONF_PASSWORD],
        },
    )
    await hass.async_block_till_done()

    for k, v in expected_result.items():
        assert result[k] == v  # type: ignore[literal-required] # expected is a subset
    for k, v in expected_entry_data.items():
        assert entry.data[k] == v


async def test_options(hass: HomeAssistant) -> None:
    """Test options produce expected data."""

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=FIXTURE_USER_INPUT, options=FIXTURE_USER_INPUT_OPTIONS
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    recipient = "+15555550000"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_RECIPIENT: recipient}
    )
    assert result["data"][CONF_NAME] == DOMAIN
    assert result["data"][CONF_RECIPIENT] == [recipient]
    assert result["data"][CONF_UNAUTHENTICATED_MODE] is False
