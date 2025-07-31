"""Test downloader action."""

from http import HTTPStatus
from typing import Any
from unittest.mock import mock_open, patch

import pytest
from requests import Request
import requests_mock

from homeassistant.components.downloader.const import (
    ATTR_AUTH_PASSWORD,
    ATTR_AUTH_TYPE,
    ATTR_AUTH_USERNAME,
    ATTR_SUBDIR,
    ATTR_URL,
    DOMAIN,
    SERVICE_DOWNLOAD_FILE,
)
from homeassistant.const import HTTP_BASIC_AUTHENTICATION, HTTP_DIGEST_AUTHENTICATION
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError


def no_authorization_request_matcher(request: Request):
    """Match requests with no auth header."""
    return "Authorization" not in request.headers


def authorization_request_matcher(request: Request):
    """Match requests with an auth header."""
    return "Authorization" in request.headers


@pytest.mark.usefixtures("loaded_config_entry")
async def test_service_call(hass: HomeAssistant) -> None:
    """Test downloader action."""

    TEST_URL = "http://example.com/resource"

    with requests_mock.Mocker() as auth_requests_mock:
        auth_requests_mock.get(
            TEST_URL,
            status_code=HTTPStatus.OK,
        )

        with patch("builtins.open", new=mock_open(), create=True):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_DOWNLOAD_FILE,
                {
                    ATTR_URL: TEST_URL,
                    ATTR_AUTH_TYPE: HTTP_BASIC_AUTHENTICATION,
                    ATTR_AUTH_USERNAME: "test",
                    ATTR_AUTH_PASSWORD: "test",
                },
                blocking=True,
            )

        assert auth_requests_mock.called


@pytest.mark.parametrize(
    ("extra_args", "error_code"),
    [
        ({ATTR_SUBDIR: "~"}, "invalid_subdir"),
        ({ATTR_AUTH_TYPE: HTTP_BASIC_AUTHENTICATION}, "missing_credentials"),
        ({ATTR_AUTH_TYPE: HTTP_DIGEST_AUTHENTICATION}, "missing_credentials"),
    ],
)
@pytest.mark.usefixtures("loaded_config_entry")
async def test_validation(
    hass: HomeAssistant, extra_args: dict[str, Any], error_code: str
) -> None:
    """Test invalid subdirectory in downloader action."""

    TEST_URL = "http://example.com/resource"

    with pytest.raises(ServiceValidationError) as exc_info:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DOWNLOAD_FILE,
            {ATTR_URL: TEST_URL, **extra_args},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == error_code


@pytest.mark.usefixtures("loaded_config_entry")
async def test_basic_auth(hass: HomeAssistant) -> None:
    """Test basic authentication in downloader action."""

    TEST_URL = "http://example.com/protected-resource"

    with requests_mock.Mocker() as auth_requests_mock:
        auth_requests_mock.get(
            TEST_URL,
            additional_matcher=no_authorization_request_matcher,
            headers={"WWW-Authenticate": 'Basic realm="example.com"'},
            status_code=HTTPStatus.UNAUTHORIZED,
        )

        auth_requests_mock.get(
            TEST_URL,
            additional_matcher=authorization_request_matcher,
            status_code=HTTPStatus.OK,
        )

        with patch("builtins.open", new=mock_open(), create=True):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_DOWNLOAD_FILE,
                {
                    ATTR_URL: TEST_URL,
                    ATTR_AUTH_TYPE: HTTP_BASIC_AUTHENTICATION,
                    ATTR_AUTH_USERNAME: "test",
                    ATTR_AUTH_PASSWORD: "test",
                },
                blocking=True,
            )

        assert auth_requests_mock.called

        assert (
            "Authorization" in auth_requests_mock.last_request.headers
            and auth_requests_mock.last_request.headers["Authorization"].startswith(
                "Basic"
            )
        )


@pytest.mark.usefixtures("loaded_config_entry")
async def test_digest_auth(hass: HomeAssistant) -> None:
    """Test digest authentication in downloader action."""

    TEST_URL = "http://example.com/protected-resource"

    with requests_mock.Mocker() as auth_requests_mock:
        auth_requests_mock.get(
            TEST_URL,
            additional_matcher=no_authorization_request_matcher,
            headers={"WWW-Authenticate": 'Digest realm="example.com", nonce="test"'},
            status_code=HTTPStatus.UNAUTHORIZED,
        )

        auth_requests_mock.get(
            TEST_URL,
            additional_matcher=authorization_request_matcher,
            status_code=HTTPStatus.OK,
        )

        with patch("builtins.open", new=mock_open(), create=True):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_DOWNLOAD_FILE,
                {
                    ATTR_URL: TEST_URL,
                    ATTR_AUTH_TYPE: HTTP_DIGEST_AUTHENTICATION,
                    ATTR_AUTH_USERNAME: "test",
                    ATTR_AUTH_PASSWORD: "test",
                },
                blocking=True,
            )

        assert auth_requests_mock.called

        assert (
            "Authorization" in auth_requests_mock.last_request.headers
            and auth_requests_mock.last_request.headers["Authorization"].startswith(
                "Digest"
            )
        )
