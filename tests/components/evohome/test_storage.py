"""Tests for evohome token/session storage load & save."""

from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Final, TypedDict
from unittest.mock import MagicMock, patch

from evohomeasync.auth import (
    SZ_SESSION_ID,
    SZ_SESSION_ID_EXPIRES,
    AbstractSessionManager,
)
from evohomeasync2.auth import (
    SZ_ACCESS_TOKEN,
    SZ_ACCESS_TOKEN_EXPIRES,
    SZ_REFRESH_TOKEN,
    AbstractTokenManager,
)
import pytest

from homeassistant.components.evohome.const import DOMAIN, STORAGE_KEY, STORAGE_VER
from homeassistant.components.evohome.storage import TokenManager, _TokenStoreT
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .const import ACCESS_TOKEN, REFRESH_TOKEN, SESSION_ID, USERNAME


class _EmptyStoreT(TypedDict):
    pass


def dt_pair(dt_dtm: datetime) -> tuple[datetime, str]:
    """Return a datetime without milliseconds and its string representation."""
    dt_str = dt_dtm.isoformat(timespec="seconds")  # e.g. 2024-07-28T00:57:29+01:00
    return dt_util.parse_datetime(dt_str, raise_on_error=True), dt_str


ACCESS_TOKEN_EXP_DTM, ACCESS_TOKEN_EXP_STR = dt_pair(dt_util.now() + timedelta(hours=1))
SESSION_ID_EXP_DTM, SESSION_ID_EXP_STR = dt_pair(dt_util.now() - timedelta(hours=1))

USERNAME_DIFF: Final = f"not_{USERNAME}"
USERNAME_SAME: Final = USERNAME

_TEST_STORAGE_BASE: Final[_TokenStoreT] = {
    CONF_USERNAME: USERNAME_SAME,
    SZ_REFRESH_TOKEN: REFRESH_TOKEN,
    SZ_ACCESS_TOKEN: ACCESS_TOKEN,
    SZ_ACCESS_TOKEN_EXPIRES: ACCESS_TOKEN_EXP_STR,
}

TEST_STORAGE_DATA: Final[dict[str, _TokenStoreT]] = {  # type: ignore[assignment]
    "sans_session_id": _TEST_STORAGE_BASE,
    "with_session_id": _TEST_STORAGE_BASE | {SZ_SESSION_ID: SESSION_ID},
    "past_session_id": _TEST_STORAGE_BASE
    | {
        SZ_SESSION_ID: SESSION_ID,
        SZ_SESSION_ID_EXPIRES: SESSION_ID_EXP_STR,
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

# Expected session_id in storage after setup, keyed by TEST_STORAGE_DATA entry.
# A missing or expired cached session is replaced; a valid cached session is kept.
EXPECTED_SESSION_ID: Final[dict[str, str]] = {
    "sans_session_id": f"new_{SESSION_ID}",
    "with_session_id": SESSION_ID,
    "past_session_id": f"new_{SESSION_ID}",
}


async def _mock_fetch_access_token(self: AbstractTokenManager) -> None:
    """Set new access-token attrs without making HTTP requests."""
    self._access_token = f"new_{ACCESS_TOKEN}"
    self._access_token_expires = dt_util.now() + timedelta(seconds=1800)
    self._refresh_token = f"new_{REFRESH_TOKEN}"


async def _mock_fetch_session_id(self: AbstractSessionManager) -> None:
    """Set new session-id attrs without making HTTP requests."""
    self._session_id = f"new_{SESSION_ID}"
    self._session_id_expires = dt_util.now() + timedelta(minutes=15)
    self._user_info = {}  # type: ignore[reportAttributeAccessIssue]


@contextmanager
def _mock_token_requests():
    with (
        patch.object(
            AbstractTokenManager, "fetch_access_token", _mock_fetch_access_token
        ),
        patch.object(
            AbstractSessionManager, "fetch_session_id", _mock_fetch_session_id
        ),
    ):
        yield


def _make_token_manager(hass: HomeAssistant, username: str = USERNAME) -> TokenManager:
    return TokenManager(hass, username, "password", MagicMock())


async def _exercise(tm: TokenManager) -> None:
    """Drive the same token/session checks the integration runs at startup."""
    with _mock_token_requests():
        await tm.get_access_token()
        await tm.get_session_id()


@pytest.mark.parametrize("idx", TEST_STORAGE_NULL)
async def test_auth_tokens_null(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    idx: str,
) -> None:
    """Test credentials manager when cache is empty."""
    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": TEST_STORAGE_NULL[idx]}

    await _exercise(_make_token_manager(hass))

    data: _TokenStoreT = hass_storage[DOMAIN]["data"]

    # Confirm the expected tokens were cached to storage...
    assert data[CONF_USERNAME] == USERNAME_SAME
    assert data[SZ_REFRESH_TOKEN] == f"new_{REFRESH_TOKEN}"
    assert data[SZ_ACCESS_TOKEN] == f"new_{ACCESS_TOKEN}"
    assert (
        dt_util.parse_datetime(data[SZ_ACCESS_TOKEN_EXPIRES], raise_on_error=True)
        > dt_util.now()
    )

    # Confirm the expected session id was cached to storage...
    assert data.get(SZ_SESSION_ID) == f"new_{SESSION_ID}"
    assert (session_expires := data.get(SZ_SESSION_ID_EXPIRES)) is not None
    assert dt_util.parse_datetime(session_expires, raise_on_error=True) > dt_util.now()


@pytest.mark.parametrize("idx", TEST_STORAGE_DATA)
async def test_auth_tokens_same(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    idx: str,
) -> None:
    """Test credentials manager when cache contains valid data for this user."""
    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": TEST_STORAGE_DATA[idx]}

    await _exercise(_make_token_manager(hass))

    data: _TokenStoreT = hass_storage[DOMAIN]["data"]

    # Confirm the expected tokens were cached to storage...
    assert data[CONF_USERNAME] == USERNAME_SAME
    assert data[SZ_REFRESH_TOKEN] == REFRESH_TOKEN
    assert data[SZ_ACCESS_TOKEN] == ACCESS_TOKEN
    assert dt_util.parse_datetime(data[SZ_ACCESS_TOKEN_EXPIRES]) == ACCESS_TOKEN_EXP_DTM

    # Confirm the expected session id was cached to storage...
    assert data.get(SZ_SESSION_ID) == EXPECTED_SESSION_ID[idx]


@pytest.mark.parametrize("idx", TEST_STORAGE_DATA)
async def test_auth_tokens_past(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    idx: str,
) -> None:
    """Test credentials manager when cache contains expired data for this user."""
    _, dt_str = dt_pair(dt_util.now() - timedelta(hours=1))

    test_data = TEST_STORAGE_DATA[idx].copy()  # shallow copy is OK here
    test_data[SZ_ACCESS_TOKEN_EXPIRES] = dt_str

    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": test_data}

    await _exercise(_make_token_manager(hass))

    data: _TokenStoreT = hass_storage[DOMAIN]["data"]

    # Confirm the expected tokens were cached to storage...
    assert data[CONF_USERNAME] == USERNAME_SAME
    assert data[SZ_REFRESH_TOKEN] == f"new_{REFRESH_TOKEN}"
    assert data[SZ_ACCESS_TOKEN] == f"new_{ACCESS_TOKEN}"
    assert (
        dt_util.parse_datetime(data[SZ_ACCESS_TOKEN_EXPIRES], raise_on_error=True)
        > dt_util.now()
    )

    # Confirm the expected session id was cached to storage...
    assert data.get(SZ_SESSION_ID) == EXPECTED_SESSION_ID[idx]


@pytest.mark.parametrize("idx", TEST_STORAGE_DATA)
async def test_auth_tokens_diff(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    idx: str,
) -> None:
    """Test credentials manager when cache contains data for a different user."""
    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": TEST_STORAGE_DATA[idx]}

    await _exercise(_make_token_manager(hass, USERNAME_DIFF))

    data: _TokenStoreT = hass_storage[DOMAIN]["data"]

    # Confirm the expected tokens were cached to storage...
    assert data[CONF_USERNAME] == USERNAME_DIFF
    assert data[SZ_REFRESH_TOKEN] == f"new_{REFRESH_TOKEN}"
    assert data[SZ_ACCESS_TOKEN] == f"new_{ACCESS_TOKEN}"
    assert (
        dt_util.parse_datetime(data[SZ_ACCESS_TOKEN_EXPIRES], raise_on_error=True)
        > dt_util.now()
    )

    # Confirm the expected session id was cached to storage...
    assert data.get(SZ_SESSION_ID) == f"new_{SESSION_ID}"
    assert (session_expires := data.get(SZ_SESSION_ID_EXPIRES)) is not None
    assert dt_util.parse_datetime(session_expires, raise_on_error=True) > dt_util.now()


async def test_session_id_loads_store(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
) -> None:
    """Test that get_session_id loads the store when called before get_access_token."""
    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": None}

    tm = _make_token_manager(hass)
    with _mock_token_requests():
        await tm.get_session_id()

    data: dict[str, Any] = hass_storage[DOMAIN]["data"]
    assert data[SZ_SESSION_ID] == f"new_{SESSION_ID}"
