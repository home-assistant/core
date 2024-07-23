"""Tests for HTTP session."""

from collections.abc import Callable
import logging
from typing import Any
from unittest.mock import patch

from aiohttp import web
from aiohttp.test_utils import make_mocked_request
import pytest

from homeassistant.auth.session import SESSION_ID
from homeassistant.components.http.session import (
    COOKIE_NAME,
    HomeAssistantCookieStorage,
)
from homeassistant.core import HomeAssistant


def fake_request_with_strict_connection_cookie(cookie_value: str) -> web.Request:
    """Return a fake request with a strict connection cookie."""
    request = make_mocked_request(
        "GET", "/", headers={"Cookie": f"{COOKIE_NAME}={cookie_value}"}
    )
    assert COOKIE_NAME in request.cookies
    return request


@pytest.fixture
def cookie_storage(hass: HomeAssistant) -> HomeAssistantCookieStorage:
    """Fixture for the cookie storage."""
    return HomeAssistantCookieStorage(hass)


def _encrypt_cookie_data(cookie_storage: HomeAssistantCookieStorage, data: Any) -> str:
    """Encrypt cookie data."""
    cookie_data = cookie_storage._encoder(data).encode("utf-8")
    return cookie_storage._fernet.encrypt(cookie_data).decode("utf-8")


@pytest.mark.parametrize(
    "func",
    [
        lambda _: "invalid",
        lambda storage: _encrypt_cookie_data(storage, "bla"),
        lambda storage: _encrypt_cookie_data(storage, None),
    ],
)
async def test_load_session_modified_cookies(
    cookie_storage: HomeAssistantCookieStorage,
    caplog: pytest.LogCaptureFixture,
    func: Callable[[HomeAssistantCookieStorage], str],
) -> None:
    """Test that on modified cookies the session is empty and the request will be logged for ban."""
    request = fake_request_with_strict_connection_cookie(func(cookie_storage))
    with patch(
        "homeassistant.components.http.session.process_wrong_login",
    ) as mock_process_wrong_login:
        session = await cookie_storage.load_session(request)
        assert session.empty
        assert (
            "homeassistant.components.http.session",
            logging.WARNING,
            "Cannot decrypt/parse cookie value",
        ) in caplog.record_tuples
        mock_process_wrong_login.assert_called()


async def test_load_session_validate_session(
    hass: HomeAssistant,
    cookie_storage: HomeAssistantCookieStorage,
) -> None:
    """Test load session validates the session."""
    session = await cookie_storage.new_session()
    session[SESSION_ID] = "bla"
    request = fake_request_with_strict_connection_cookie(
        _encrypt_cookie_data(cookie_storage, cookie_storage._get_session_data(session))
    )

    with patch.object(
        hass.auth.session, "async_validate_strict_connection_session", return_value=True
    ) as mock_validate:
        session = await cookie_storage.load_session(request)
        assert not session.empty
        assert session[SESSION_ID] == "bla"
        mock_validate.assert_called_with(session)

        # verify lru_cache is working
        mock_validate.reset_mock()
        await cookie_storage.load_session(request)
        mock_validate.assert_not_called()

    session = await cookie_storage.new_session()
    session[SESSION_ID] = "something"
    request = fake_request_with_strict_connection_cookie(
        _encrypt_cookie_data(cookie_storage, cookie_storage._get_session_data(session))
    )

    with patch.object(
        hass.auth.session,
        "async_validate_strict_connection_session",
        return_value=False,
    ):
        session = await cookie_storage.load_session(request)
        assert session.empty
        assert SESSION_ID not in session
        assert session._changed
