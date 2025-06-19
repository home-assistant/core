"""Test downloader action."""

from http import HTTPStatus
from unittest.mock import mock_open, patch

import requests_mock

from homeassistant.components.downloader.const import (
    ATTR_DIGEST_AUTH,
    ATTR_DIGEST_PASSWORD,
    ATTR_DIGEST_USERNAME,
    ATTR_URL,
    CONF_DOWNLOAD_DIR,
    DOMAIN,
    SERVICE_DOWNLOAD_FILE,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


def digest_challenge_matcher(request):
    """Match requests with no auth header."""
    return "Authorization" not in request.headers


def digest_response_matcher(request):
    """Match requests with an auth header."""
    return "Authorization" in request.headers


async def test_digest_auth(hass: HomeAssistant) -> None:
    """Test digest authentication in downloader action."""

    TEST_URL = "http://example.com/protected-resource"

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_DOWNLOAD_DIR: "/test_dir",
        },
    )
    config_entry.add_to_hass(hass)
    with patch("os.path.isdir", return_value=True):
        await hass.config_entries.async_setup(config_entry.entry_id)

    with requests_mock.Mocker() as mock:
        mock.get(
            TEST_URL,
            additional_matcher=digest_challenge_matcher,
            headers={"WWW-Authenticate": 'Digest realm="example.com", nonce="test"'},
            status_code=HTTPStatus.UNAUTHORIZED,
        )

        mock.get(
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
                    ATTR_DIGEST_AUTH: True,
                    ATTR_DIGEST_USERNAME: "test",
                    ATTR_DIGEST_PASSWORD: "test",
                },
                blocking=True,
            )

        assert mock.called

        assert (
            "Authorization" in mock.last_request.headers
            and mock.last_request.headers["Authorization"].startswith("Digest")
        )
