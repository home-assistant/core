"""The tests for evohome storage load & save."""

from typing import Any, Final
from unittest.mock import patch

import pytest

from homeassistant.components.evohome import (
    ACCESS_TOKEN_EXPIRES,
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
    SZ_SESSION_ID,
    USER_DATA,
    EvoSession,
    dt_aware_to_naive,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .conftest import mock_get

DIFF_EMAIL_ADDRESS: Final = "diff_user@email.com"
SAME_EMAIL_ADDRESS: Final = "same_user@email.com"

REFRESH_TOKEN: Final = "jg68ZCKYdxEI3fF..."
ACCESS_TOKEN: Final = "1dc7z657UKzbhKA..."

ACCESS_TOKEN_EXPIRES_STR: Final = "2024-06-10T22:05:54+00:00"  # tests need UTC TZ
ACCESS_TOKEN_EXPIRES_DTM: Final = dt_aware_to_naive(
    dt_util.parse_datetime(ACCESS_TOKEN_EXPIRES_STR)  # type: ignore[arg-type]
)

SESSION_ID: Final = "F7181186..."

TEST_CONFIG: Final = {
    CONF_USERNAME: SAME_EMAIL_ADDRESS,
    CONF_PASSWORD: "password",
}


TEST_DATA: Final = {
    "00": None,
    "01": {},
    "10": {
        "username": SAME_EMAIL_ADDRESS,
        "refresh_token": REFRESH_TOKEN,
        "access_token": ACCESS_TOKEN,
        "access_token_expires": ACCESS_TOKEN_EXPIRES_STR,
    },
    "11": {
        "username": SAME_EMAIL_ADDRESS,
        "refresh_token": REFRESH_TOKEN,
        "access_token": ACCESS_TOKEN,
        "access_token_expires": ACCESS_TOKEN_EXPIRES_STR,
        "user_data": {"sessionId": SESSION_ID},
    },
}


@pytest.mark.parametrize("idx", TEST_DATA)
async def test_load_auth_tokens_same(
    hass: HomeAssistant, hass_storage: dict[str, Any], idx: str
) -> None:
    """Test restoring authentication tokens when matching account."""

    hass_storage[DOMAIN] = {
        "version": 1,
        "minor_version": 1,
        "key": "evohome",
        "data": TEST_DATA[idx],
    }

    # Load access tokens and session_id from the store
    sess = EvoSession(hass)
    await sess._load_auth_tokens(SAME_EMAIL_ADDRESS)

    # Construct the expected authentication attrs: tokens & session_id
    app_storage = (TEST_DATA[idx] or {}).copy()
    app_storage.pop(CONF_USERNAME, None)

    if idx in ("10", "11"):  # HACK: validate the test, not the code
        assert "username" in TEST_DATA[idx]  # type: ignore[operator]
        assert "username" not in app_storage

    if app_storage.get(ACCESS_TOKEN_EXPIRES) is not None and (
        expires := dt_util.parse_datetime(app_storage[ACCESS_TOKEN_EXPIRES])  # type: ignore[call-overload]
    ):
        app_storage[ACCESS_TOKEN_EXPIRES] = dt_aware_to_naive(expires)  # type: ignore[assignment]

    user_data: dict[str, str] = app_storage.pop(USER_DATA, {})  # type: ignore[assignment]

    # Assert the restored authentication attrs: tokens & session_id
    assert sess.session_id == user_data.get(SZ_SESSION_ID)
    assert sess._tokens == app_storage

    if idx in ("10", "11"):  # HACK: validate the test, not the code
        assert "username" in TEST_DATA[idx]  # type: ignore[operator]


@pytest.mark.parametrize("idx", TEST_DATA)
async def test_load_auth_tokens_diff(
    hass: HomeAssistant, hass_storage: dict[str, Any], idx: str
) -> None:
    """Test restoring authentication tokens when unmatched account."""

    hass_storage[DOMAIN] = {
        "version": 1,
        "minor_version": 1,
        "key": "evohome",
        "data": TEST_DATA[idx],
    }

    sess = EvoSession(hass)

    # Load access tokens and session_id from the store
    await sess._load_auth_tokens(DIFF_EMAIL_ADDRESS)

    # Assert the restored authentication attrs: tokens & session_id
    assert sess.session_id is None
    assert sess._tokens == {}


@patch("evohomeasync2.broker.Broker.get", mock_get)
async def test_save_auth_tokens(
    hass: HomeAssistant, hass_storage: dict[str, Any]
) -> None:
    """Test saving authentication tokens."""

    dt_util.set_default_time_zone(dt_util.UTC)

    with (
        patch("evohomeasync2.EvohomeClient.refresh_token", REFRESH_TOKEN),
        patch("evohomeasync2.EvohomeClient.access_token", ACCESS_TOKEN),
        patch(
            "evohomeasync2.EvohomeClient.access_token_expires", ACCESS_TOKEN_EXPIRES_DTM
        ),
    ):
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: TEST_CONFIG})
        await hass.async_block_till_done()

    assert hass_storage[DOMAIN]["data"] == TEST_DATA["10"]
