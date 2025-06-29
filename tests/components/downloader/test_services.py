"""Test downloader action."""

from http import HTTPStatus
from unittest.mock import mock_open, patch

import pytest
from requests_mock import Mocker

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


def digest_challenge_matcher(request):
    """Match requests with no auth header."""
    return "Authorization" not in request.headers


def digest_response_matcher(request):
    """Match requests with an auth header."""
    return "Authorization" in request.headers


@pytest.mark.usefixtures("loaded_config_entry")
async def test_service_call(hass: HomeAssistant, requests_mock: Mocker) -> None:
    """Test downloader action."""

    TEST_URL = "http://example.com/resource"

    requests_mock.get(
        TEST_URL,
        additional_matcher=digest_response_matcher,
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

    assert requests_mock.called


@pytest.mark.usefixtures("loaded_config_entry")
async def test_invalid_subdir(hass: HomeAssistant, requests_mock: Mocker) -> None:
    """Test invalid subdirectory in downloader action."""

    TEST_URL = "http://example.com/resource"

    requests_mock.get(
        TEST_URL,
        status_code=HTTPStatus.OK,
    )

    with (
        pytest.raises(
            ServiceValidationError,
            match="Subdirectory must be valid",
        ),
        patch("builtins.open", new=mock_open(), create=True),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DOWNLOAD_FILE,
            {ATTR_URL: TEST_URL, ATTR_SUBDIR: "~"},
            blocking=True,
        )

    assert not requests_mock.called


@pytest.mark.usefixtures("loaded_config_entry")
async def test_invalid_credentials(hass: HomeAssistant, requests_mock: Mocker) -> None:
    """Test invalid credentials in downloader action."""

    TEST_URL = "http://example.com/resource"

    requests_mock.get(
        TEST_URL,
        status_code=HTTPStatus.OK,
    )

    with (
        pytest.raises(
            ServiceValidationError,
            match="Username and password are required",
        ),
        patch("builtins.open", new=mock_open(), create=True),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_DOWNLOAD_FILE,
            {
                ATTR_URL: TEST_URL,
                ATTR_AUTH_TYPE: HTTP_BASIC_AUTHENTICATION,
            },
            blocking=True,
        )

    assert not requests_mock.called


@pytest.mark.usefixtures("loaded_config_entry")
async def test_basic_auth(hass: HomeAssistant, auth_requests_mock: Mocker) -> None:
    """Test basic authentication in downloader action."""

    TEST_URL = "http://example.com/protected-resource"

    auth_requests_mock.get(
        TEST_URL,
        additional_matcher=digest_challenge_matcher,
        headers={"WWW-Authenticate": 'Basic realm="example.com"'},
        status_code=HTTPStatus.UNAUTHORIZED,
    )

    auth_requests_mock.get(
        TEST_URL,
        additional_matcher=digest_response_matcher,
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
        and auth_requests_mock.last_request.headers["Authorization"].startswith("Basic")
    )


@pytest.mark.usefixtures("loaded_config_entry")
async def test_digest_auth(hass: HomeAssistant, auth_requests_mock: Mocker) -> None:
    """Test digest authentication in downloader action."""

    TEST_URL = "http://example.com/protected-resource"

    auth_requests_mock.get(
        TEST_URL,
        additional_matcher=digest_challenge_matcher,
        headers={"WWW-Authenticate": 'Digest realm="example.com", nonce="test"'},
        status_code=HTTPStatus.UNAUTHORIZED,
    )

    auth_requests_mock.get(
        TEST_URL,
        additional_matcher=digest_response_matcher,
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
