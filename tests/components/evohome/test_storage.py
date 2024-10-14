"""The tests for evohome storage load & save."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Final, NotRequired, TypedDict

import pytest

from homeassistant.components.evohome import (
    CONF_USERNAME,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VER,
    dt_aware_to_naive,
)
from homeassistant.core import HomeAssistant
import homeassistant.util.dt as dt_util

from .conftest import setup_evohome
from .const import ACCESS_TOKEN, REFRESH_TOKEN, SESSION_ID, USERNAME


class _SessionDataT(TypedDict):
    sessionId: str


class _TokenStoreT(TypedDict):
    username: str
    refresh_token: str
    access_token: str
    access_token_expires: str  # 2024-07-27T23:57:30+01:00
    user_data: NotRequired[_SessionDataT]


class _EmptyStoreT(TypedDict):
    pass


SZ_USERNAME: Final = "username"
SZ_REFRESH_TOKEN: Final = "refresh_token"
SZ_ACCESS_TOKEN: Final = "access_token"
SZ_ACCESS_TOKEN_EXPIRES: Final = "access_token_expires"
SZ_USER_DATA: Final = "user_data"


def dt_pair(dt_dtm: datetime) -> tuple[datetime, str]:
    """Return a datetime without milliseconds and its string representation."""
    dt_str = dt_dtm.isoformat(timespec="seconds")  # e.g. 2024-07-28T00:57:29+01:00
    return dt_util.parse_datetime(dt_str, raise_on_error=True), dt_str


ACCESS_TOKEN_EXP_DTM, ACCESS_TOKEN_EXP_STR = dt_pair(dt_util.now() + timedelta(hours=1))

USERNAME_DIFF: Final = f"not_{USERNAME}"
USERNAME_SAME: Final = USERNAME

TEST_STORAGE_DATA: Final[dict[str, _TokenStoreT]] = {
    "sans_session_id": {
        SZ_USERNAME: USERNAME_SAME,
        SZ_REFRESH_TOKEN: REFRESH_TOKEN,
        SZ_ACCESS_TOKEN: ACCESS_TOKEN,
        SZ_ACCESS_TOKEN_EXPIRES: ACCESS_TOKEN_EXP_STR,
    },
    "with_session_id": {
        SZ_USERNAME: USERNAME_SAME,
        SZ_REFRESH_TOKEN: REFRESH_TOKEN,
        SZ_ACCESS_TOKEN: ACCESS_TOKEN,
        SZ_ACCESS_TOKEN_EXPIRES: ACCESS_TOKEN_EXP_STR,
        SZ_USER_DATA: {"sessionId": SESSION_ID},
    },
}

TEST_STORAGE_NULL: Final[dict[str, _EmptyStoreT | None]] = {
    "store_is_absent": None,
    "store_was_reset": {},
}

DOMAIN_STORAGE_BASE: Final = {
    "version": STORAGE_VER,
    "minor_version": 1,
    "key": STORAGE_KEY,
}


@pytest.mark.parametrize("install", ["minimal"])
@pytest.mark.parametrize("idx", TEST_STORAGE_NULL)
async def test_auth_tokens_null(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    config: dict[str, str],
    idx: str,
    install: str,
) -> None:
    """Test loading/saving authentication tokens when no cached tokens in the store."""

    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": TEST_STORAGE_NULL[idx]}

    async for mock_client in setup_evohome(hass, config, install=install):
        # Confirm client was instantiated without tokens, as cache was empty...
        assert SZ_REFRESH_TOKEN not in mock_client.call_args.kwargs
        assert SZ_ACCESS_TOKEN not in mock_client.call_args.kwargs
        assert SZ_ACCESS_TOKEN_EXPIRES not in mock_client.call_args.kwarg

    # Confirm the expected tokens were cached to storage...
    data: _TokenStoreT = hass_storage[DOMAIN]["data"]

    assert data[SZ_USERNAME] == USERNAME_SAME
    assert data[SZ_REFRESH_TOKEN] == f"new_{REFRESH_TOKEN}"
    assert data[SZ_ACCESS_TOKEN] == f"new_{ACCESS_TOKEN}"
    assert (
        dt_util.parse_datetime(data[SZ_ACCESS_TOKEN_EXPIRES], raise_on_error=True)
        > dt_util.now()
    )


@pytest.mark.parametrize("install", ["minimal"])
@pytest.mark.parametrize("idx", TEST_STORAGE_DATA)
async def test_auth_tokens_same(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    config: dict[str, str],
    idx: str,
    install: str,
) -> None:
    """Test loading/saving authentication tokens when matching username."""

    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": TEST_STORAGE_DATA[idx]}

    async for mock_client in setup_evohome(hass, config, install=install):
        # Confirm client was instantiated with the cached tokens...
        assert mock_client.call_args.kwargs[SZ_REFRESH_TOKEN] == REFRESH_TOKEN
        assert mock_client.call_args.kwargs[SZ_ACCESS_TOKEN] == ACCESS_TOKEN
        assert mock_client.call_args.kwargs[
            SZ_ACCESS_TOKEN_EXPIRES
        ] == dt_aware_to_naive(ACCESS_TOKEN_EXP_DTM)

    # Confirm the expected tokens were cached to storage...
    data: _TokenStoreT = hass_storage[DOMAIN]["data"]

    assert data[SZ_USERNAME] == USERNAME_SAME
    assert data[SZ_REFRESH_TOKEN] == REFRESH_TOKEN
    assert data[SZ_ACCESS_TOKEN] == ACCESS_TOKEN
    assert dt_util.parse_datetime(data[SZ_ACCESS_TOKEN_EXPIRES]) == ACCESS_TOKEN_EXP_DTM


@pytest.mark.parametrize("install", ["minimal"])
@pytest.mark.parametrize("idx", TEST_STORAGE_DATA)
async def test_auth_tokens_past(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    config: dict[str, str],
    idx: str,
    install: str,
) -> None:
    """Test loading/saving authentication tokens with matching username, but expired."""

    dt_dtm, dt_str = dt_pair(dt_util.now() - timedelta(hours=1))

    # make this access token have expired in the past...
    test_data = TEST_STORAGE_DATA[idx].copy()  # shallow copy is OK here
    test_data[SZ_ACCESS_TOKEN_EXPIRES] = dt_str

    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": test_data}

    async for mock_client in setup_evohome(hass, config, install=install):
        # Confirm client was instantiated with the cached tokens...
        assert mock_client.call_args.kwargs[SZ_REFRESH_TOKEN] == REFRESH_TOKEN
        assert mock_client.call_args.kwargs[SZ_ACCESS_TOKEN] == ACCESS_TOKEN
        assert mock_client.call_args.kwargs[
            SZ_ACCESS_TOKEN_EXPIRES
        ] == dt_aware_to_naive(dt_dtm)

    # Confirm the expected tokens were cached to storage...
    data: _TokenStoreT = hass_storage[DOMAIN]["data"]

    assert data[SZ_USERNAME] == USERNAME_SAME
    assert data[SZ_REFRESH_TOKEN] == REFRESH_TOKEN
    assert data[SZ_ACCESS_TOKEN] == f"new_{ACCESS_TOKEN}"
    assert (
        dt_util.parse_datetime(data[SZ_ACCESS_TOKEN_EXPIRES], raise_on_error=True)
        > dt_util.now()
    )


@pytest.mark.parametrize("install", ["minimal"])
@pytest.mark.parametrize("idx", TEST_STORAGE_DATA)
async def test_auth_tokens_diff(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    config: dict[str, str],
    idx: str,
    install: str,
) -> None:
    """Test loading/saving authentication tokens when unmatched username."""

    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": TEST_STORAGE_DATA[idx]}

    async for mock_client in setup_evohome(
        hass, config | {CONF_USERNAME: USERNAME_DIFF}, install=install
    ):
        # Confirm client was instantiated without tokens, as username was different...
        assert SZ_REFRESH_TOKEN not in mock_client.call_args.kwargs
        assert SZ_ACCESS_TOKEN not in mock_client.call_args.kwargs
        assert SZ_ACCESS_TOKEN_EXPIRES not in mock_client.call_args.kwarg

    # Confirm the expected tokens were cached to storage...
    data: _TokenStoreT = hass_storage[DOMAIN]["data"]

    assert data[SZ_USERNAME] == USERNAME_DIFF
    assert data[SZ_REFRESH_TOKEN] == f"new_{REFRESH_TOKEN}"
    assert data[SZ_ACCESS_TOKEN] == f"new_{ACCESS_TOKEN}"
    assert (
        dt_util.parse_datetime(data[SZ_ACCESS_TOKEN_EXPIRES], raise_on_error=True)
        > dt_util.now()
    )
