"""The tests for Evohome."""

from __future__ import annotations

from http import HTTPStatus
import logging
from unittest.mock import Mock, patch

import aiohttp
from evohomeasync2 import EvohomeClient, exceptions as exc
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.evohome.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import mock_post_request
from .const import TEST_INSTALLS

_MSG_429 = (
    "You have exceeded the server's API rate limit. Wait a while "
    "and try again (consider reducing your polling interval)."
)
_MSG_OTH = (
    "Unable to contact the vendor's server. Check your network "
    "and review the vendor's status page, https://status.resideo.com."
)
_MSG_USR = (
    "Failed to authenticate. Check the username/password. Note that some "
    "special characters accepted via the vendor's website are not valid here."
)

LOG_HINT_429_CREDS = ("evohome.credentials", logging.ERROR, _MSG_429)
LOG_HINT_OTH_CREDS = ("evohome.credentials", logging.ERROR, _MSG_OTH)
LOG_HINT_USR_CREDS = ("evohome.credentials", logging.ERROR, _MSG_USR)

LOG_HINT_429_AUTH = ("evohome.auth", logging.ERROR, _MSG_429)
LOG_HINT_OTH_AUTH = ("evohome.auth", logging.ERROR, _MSG_OTH)
LOG_HINT_USR_AUTH = ("evohome.auth", logging.ERROR, _MSG_USR)

LOG_FAIL_CONNECTION = (
    "homeassistant.components.evohome",
    logging.ERROR,
    "Failed to fetch initial data: Authenticator response is invalid: Connection error",
)
LOG_FAIL_CREDENTIALS = (
    "homeassistant.components.evohome",
    logging.ERROR,
    "Failed to fetch initial data: "
    "Authenticator response is invalid: {'error': 'invalid_grant'}",
)
LOG_FAIL_GATEWAY = (
    "homeassistant.components.evohome",
    logging.ERROR,
    "Failed to fetch initial data: "
    "Authenticator response is invalid: 502 Bad Gateway, response=None",
)
LOG_FAIL_TOO_MANY = (
    "homeassistant.components.evohome",
    logging.ERROR,
    "Failed to fetch initial data: "
    "Authenticator response is invalid: 429 Too Many Requests, response=None",
)

LOG_FGET_CONNECTION = (
    "homeassistant.components.evohome",
    logging.ERROR,
    "Failed to fetch initial data: "
    "GET https://tccna.resideo.com/WebAPI/emea/api/v1/userAccount: "
    "Connection error",
)
LOG_FGET_GATEWAY = (
    "homeassistant.components.evohome",
    logging.ERROR,
    "Failed to fetch initial data: "
    "GET https://tccna.resideo.com/WebAPI/emea/api/v1/userAccount: "
    "502 Bad Gateway, response=None",
)
LOG_FGET_TOO_MANY = (
    "homeassistant.components.evohome",
    logging.ERROR,
    "Failed to fetch initial data: "
    "GET https://tccna.resideo.com/WebAPI/emea/api/v1/userAccount: "
    "429 Too Many Requests, response=None",
)


LOG_SETUP_FAILED = (
    "homeassistant.setup",
    logging.ERROR,
    "Setup failed for 'evohome': Integration failed to initialize.",
)

EXC_BAD_CONNECTION = aiohttp.ClientConnectionError(
    "Connection error",
)
EXC_BAD_CREDENTIALS = exc.AuthenticationFailedError(
    "Authenticator response is invalid: {'error': 'invalid_grant'}",
    status=HTTPStatus.BAD_REQUEST,
)
EXC_TOO_MANY_REQUESTS = aiohttp.ClientResponseError(
    Mock(),
    (),
    status=HTTPStatus.TOO_MANY_REQUESTS,
    message=HTTPStatus.TOO_MANY_REQUESTS.phrase,
)
EXC_BAD_GATEWAY = aiohttp.ClientResponseError(
    Mock(), (), status=HTTPStatus.BAD_GATEWAY, message=HTTPStatus.BAD_GATEWAY.phrase
)

AUTHENTICATION_TESTS: dict[Exception, list] = {
    EXC_BAD_CONNECTION: [LOG_HINT_OTH_CREDS, LOG_FAIL_CONNECTION, LOG_SETUP_FAILED],
    EXC_BAD_CREDENTIALS: [LOG_HINT_USR_CREDS, LOG_FAIL_CREDENTIALS, LOG_SETUP_FAILED],
    EXC_BAD_GATEWAY: [LOG_HINT_OTH_CREDS, LOG_FAIL_GATEWAY, LOG_SETUP_FAILED],
    EXC_TOO_MANY_REQUESTS: [LOG_HINT_429_CREDS, LOG_FAIL_TOO_MANY, LOG_SETUP_FAILED],
}

CLIENT_REQUEST_TESTS: dict[Exception, list] = {
    EXC_BAD_CONNECTION: [LOG_HINT_OTH_AUTH, LOG_FGET_CONNECTION, LOG_SETUP_FAILED],
    EXC_BAD_GATEWAY: [LOG_HINT_OTH_AUTH, LOG_FGET_GATEWAY, LOG_SETUP_FAILED],
    EXC_TOO_MANY_REQUESTS: [LOG_HINT_429_AUTH, LOG_FGET_TOO_MANY, LOG_SETUP_FAILED],
}


@pytest.mark.parametrize("exception", AUTHENTICATION_TESTS)
async def test_authentication_failure_v2(
    hass: HomeAssistant,
    config: dict[str, str],
    exception: Exception,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test failure to setup an evohome-compatible system.

    In this instance, the failure occurs in the v2 API.
    """

    with (
        patch(
            "evohome.credentials.CredentialsManagerBase._request", side_effect=exception
        ),
        caplog.at_level(logging.WARNING),
    ):
        result = await async_setup_component(hass, DOMAIN, {DOMAIN: config})

    assert result is False

    assert caplog.record_tuples == AUTHENTICATION_TESTS[exception]


@pytest.mark.parametrize("exception", CLIENT_REQUEST_TESTS)
async def test_client_request_failure_v2(
    hass: HomeAssistant,
    config: dict[str, str],
    exception: Exception,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test failure to setup an evohome-compatible system.

    In this instance, the failure occurs in the v2 API.
    """

    with (
        patch(
            "evohomeasync2.auth.CredentialsManagerBase._post_request",
            mock_post_request("default"),
        ),
        patch("evohome.auth.AbstractAuth._request", side_effect=exception),
        caplog.at_level(logging.WARNING),
    ):
        result = await async_setup_component(hass, DOMAIN, {DOMAIN: config})

    assert result is False

    assert caplog.record_tuples == CLIENT_REQUEST_TESTS[exception]


@pytest.mark.parametrize("install", [*TEST_INSTALLS, "botched"])
async def test_setup(
    hass: HomeAssistant,
    evohome: EvohomeClient,
    snapshot: SnapshotAssertion,
) -> None:
    """Test services after setup of evohome.

    Registered services vary by the type of system.
    """

    assert hass.services.async_services_for_domain(DOMAIN).keys() == snapshot
