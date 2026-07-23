"""Tests for the Beatbot API client (region-based base URL resolution)."""

from __future__ import annotations

import logging
from types import SimpleNamespace

from aiohttp import ClientResponseError
from beatbot_cloud.const import OAUTH2_TOKEN_URL, REGION_API_BASE_URL
import pytest

from homeassistant.components.beatbot.api import (
    BeatbotAPI,
    BeatbotAuthError,
    BeatbotConnectionError,
)


def _api_for_region(region: str | None) -> BeatbotAPI:
    """Build a BeatbotAPI with a config entry carrying the given region."""
    data = {} if region is None else {"region": region}
    entry = SimpleNamespace(data=data)
    # hass/session are unused at construction time; __init__ only stores them
    # and resolves the base URL from the entry.
    return BeatbotAPI(None, entry, None)


@pytest.mark.parametrize(
    ("region", "expected_base"),
    [
        ("cn", REGION_API_BASE_URL["cn"]),
        ("na", REGION_API_BASE_URL["na"]),
        ("eu", REGION_API_BASE_URL["eu"]),
    ],
)
def test_api_base_url_resolves_by_region(region: str, expected_base: str) -> None:
    """The base URL follows the entry's region claim."""
    api = _api_for_region(region)

    assert api._base_url == expected_base


@pytest.mark.parametrize(
    ("region", "error"),
    [(None, TypeError), ("unknown-region", ValueError)],
)
def test_api_rejects_missing_or_unknown_region(
    region: str | None, error: type[Exception]
) -> None:
    """A missing or unmapped region raises instead of silently falling back."""
    with pytest.raises(error):
        _api_for_region(region)


class _Response:
    """Minimal aiohttp response double for API request tests."""

    def __init__(
        self,
        body: str,
        *,
        status: int = 200,
        content_type: str = "application/json",
    ) -> None:
        self.status = status
        self.headers = {"Content-Type": content_type}
        self._body = body

    async def text(self) -> str:
        return self._body


class _Session:
    """Minimal OAuth2Session double that records request kwargs."""

    def __init__(self, response: _Response) -> None:
        self.response = response
        self.kwargs = None

    async def async_request(self, _method: str, _url: str, **kwargs):
        self.kwargs = kwargs
        return self.response


class _ErrorSession:
    """OAuth2Session double that raises a request error."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    async def async_request(self, _method: str, _url: str, **kwargs):
        raise self.error


@pytest.mark.asyncio
async def test_request_accepts_json_even_with_wrong_content_type() -> None:
    """Some gateways mislabel JSON; parse the body instead of failing MIME checks."""
    session = _Session(
        _Response(
            '{"code": 200, "data": {"devices": []}}',
            content_type="text/html; charset=utf-8",
        )
    )
    api = _api_for_region("na")
    api._session = session

    data = await api._request("GET", "/openapi/v1/ha")

    assert data == {"devices": []}
    assert session.kwargs["headers"] == {"Accept": "application/json"}


@pytest.mark.asyncio
async def test_request_reports_html_response_as_non_json() -> None:
    """HTML error pages returned with 200 become a clear retryable connection error."""
    session = _Session(
        _Response(
            "<html><title>Beatbot</title></html>",
            content_type="text/html; charset=utf-8",
        )
    )
    api = _api_for_region("na")
    api._session = session

    with pytest.raises(BeatbotConnectionError, match="API returned non-JSON response"):
        await api._request("GET", "/openapi/v1/ha")


@pytest.mark.asyncio
async def test_refresh_token_rejection_requires_reauthentication(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A terminal OAuth refresh response triggers reauth and leaves a safe log."""
    request_info = SimpleNamespace(real_url=OAUTH2_TOKEN_URL)
    error = ClientResponseError(request_info, (), status=400, message="Bad Request")
    api = _api_for_region("na")
    api._entry.entry_id = "entry-123"
    api._session = _ErrorSession(error)

    with (
        caplog.at_level(logging.WARNING, logger="homeassistant.components.beatbot.api"),
        pytest.raises(BeatbotAuthError, match="reauthentication required"),
    ):
        await api._request("GET", "/openapi/v1/ha")

    assert "OAuth token refresh rejected" in caplog.text
    assert "entry_id=entry-123" in caplog.text
    assert "refresh-token" not in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [408, 429, 500])
async def test_retryable_oauth_failure_remains_connection_error(status: int) -> None:
    """Transient token endpoint failures remain retryable connection errors."""
    request_info = SimpleNamespace(real_url=OAUTH2_TOKEN_URL)
    error = ClientResponseError(request_info, (), status=status, message="Temporary")
    api = _api_for_region("na")
    api._session = _ErrorSession(error)

    with pytest.raises(BeatbotConnectionError):
        await api._request("GET", "/openapi/v1/ha")
