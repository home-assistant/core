"""The tests for Evohome."""

from __future__ import annotations

from http import HTTPStatus
import logging
from unittest.mock import Mock, patch

import aiohttp
from evohomeasync2 import exceptions as exc
import pytest

from homeassistant.components.evohome.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import mock_post_request

from tests.common import MockConfigEntry

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

LOG_HINT_429_CREDS = ("homeassistant.components.evohome", logging.ERROR, _MSG_429)
LOG_HINT_OTH_CREDS = ("homeassistant.components.evohome", logging.ERROR, _MSG_OTH)
LOG_HINT_USR_CREDS = ("homeassistant.components.evohome", logging.ERROR, _MSG_USR)

LOG_HINT_429_AUTH = ("evohome.auth", logging.ERROR, _MSG_429)
LOG_HINT_OTH_AUTH = ("evohome.auth", logging.ERROR, _MSG_OTH)
LOG_HINT_USR_AUTH = ("evohome.auth", logging.ERROR, _MSG_USR)


EXC_BAD_CONNECTION = aiohttp.ClientConnectionError(
    "Connection error",
)
EXC_BAD_CREDENTIALS = exc.AuthenticationFailedError(
    "Authenticator response is invalid: {'error': 'invalid_grant'}",
    status=HTTPStatus.BAD_REQUEST,
)
EXC_BAD_GATEWAY = aiohttp.ClientResponseError(
    Mock(), (), status=HTTPStatus.BAD_GATEWAY, message=HTTPStatus.BAD_GATEWAY.phrase
)
EXC_TOO_MANY_REQUESTS = aiohttp.ClientResponseError(
    Mock(),
    (),
    status=HTTPStatus.TOO_MANY_REQUESTS,
    message=HTTPStatus.TOO_MANY_REQUESTS.phrase,
)


def generate_error_set(
    errors: tuple, base_msg: str = "Authenticator response is invalid: "
) -> tuple[tuple[str, int, str], ...]:
    """Generate log message tuples for common errors."""

    return tuple(
        (
            "homeassistant.components.evohome",
            logging.ERROR,
            f"Failed to fetch initial data: {base_msg}{e}",
        )
        for e in errors
    )


_AUTH_ERRORS = (
    "Connection error",
    "{'error': 'invalid_grant'}",
    "502 Bad Gateway, response=None",
    "429 Too Many Requests, response=None",
)
LOG_FAIL_CONNECTION, LOG_FAIL_CREDENTIALS, LOG_FAIL_GATEWAY, LOG_FAIL_TOO_MANY = (
    generate_error_set(
        _AUTH_ERRORS,
        base_msg="Authenticator response is invalid: ",
    )
)


_FGET_ERRORS = (
    "Connection error",
    "502 Bad Gateway, response=None",
    "429 Too Many Requests, response=None",
)
LOG_FGET_CONNECTION, LOG_FGET_GATEWAY, LOG_FGET_TOO_MANY = generate_error_set(
    _FGET_ERRORS,
    base_msg="GET https://tccna.resideo.com/WebAPI/emea/api/v1/userAccount: ",
)


AUTHENTICATION_TESTS: dict[Exception, list] = {
    EXC_BAD_CONNECTION: [LOG_HINT_OTH_CREDS, LOG_FAIL_CONNECTION],
    EXC_BAD_CREDENTIALS: [LOG_HINT_USR_CREDS, LOG_FAIL_CREDENTIALS],
    EXC_BAD_GATEWAY: [LOG_HINT_OTH_CREDS, LOG_FAIL_GATEWAY],
    EXC_TOO_MANY_REQUESTS: [LOG_HINT_429_CREDS, LOG_FAIL_TOO_MANY],
}
CLIENT_REQUEST_TESTS: dict[Exception, list] = {
    EXC_BAD_CONNECTION: [LOG_HINT_OTH_AUTH, LOG_FGET_CONNECTION],
    EXC_BAD_GATEWAY: [LOG_HINT_OTH_AUTH, LOG_FGET_GATEWAY],
    EXC_TOO_MANY_REQUESTS: [LOG_HINT_429_AUTH, LOG_FGET_TOO_MANY],
}


@pytest.mark.parametrize("exception", AUTHENTICATION_TESTS)
async def test_authentication_failure_import(
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
        await hass.async_block_till_done()  # wait for async_setup_entry()

    assert result is True  # because credentials are not tested during import
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert config_entry.state == ConfigEntryState.SETUP_ERROR

    assert caplog.record_tuples == AUTHENTICATION_TESTS[exception]


@pytest.mark.parametrize("exception", AUTHENTICATION_TESTS)
async def test_authentication_failure_config(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    exception: Exception,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test failure to setup an evohome-compatible system.

    In this instance, the failure occurs in the v2 API.
    """

    config_entry.add_to_hass(hass)

    with (
        patch(
            "evohome.credentials.CredentialsManagerBase._request", side_effect=exception
        ),
        caplog.at_level(logging.WARNING),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_ERROR

    assert caplog.record_tuples == AUTHENTICATION_TESTS[exception]


@pytest.mark.parametrize("exception", CLIENT_REQUEST_TESTS)
async def test_client_request_failure_import(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
    exception: Exception,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test failure to setup an evohome-compatible system.

    In this instance, the failure occurs in the v2 API.
    """

    with (
        patch(
            "evohomeasync2.auth.CredentialsManagerBase._post_request",
            mock_post_request(install),
        ),
        patch("evohome.auth.AbstractAuth._request", side_effect=exception),
        caplog.at_level(logging.WARNING),
    ):
        result = await async_setup_component(hass, DOMAIN, {DOMAIN: config})
        await hass.async_block_till_done()  # wait for async_setup_entry()

    assert result is True  # because credentials are not tested during import
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert config_entry.state == ConfigEntryState.SETUP_ERROR

    assert caplog.record_tuples == CLIENT_REQUEST_TESTS[exception]


@pytest.mark.parametrize("exception", CLIENT_REQUEST_TESTS)
async def test_client_request_failure_config(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    install: str,
    exception: Exception,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test failure to setup an evohome-compatible system.

    In this instance, the failure occurs in the v2 API.
    """

    config_entry.add_to_hass(hass)

    with (
        patch(
            "evohomeasync2.auth.CredentialsManagerBase._post_request",
            mock_post_request(install),
        ),
        patch("evohome.auth.AbstractAuth._request", side_effect=exception),
        caplog.at_level(logging.WARNING),
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state == ConfigEntryState.SETUP_ERROR

    assert caplog.record_tuples == CLIENT_REQUEST_TESTS[exception]
