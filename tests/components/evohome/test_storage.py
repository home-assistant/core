"""The tests for evohome storage load & save."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Final, NotRequired, TypedDict
from unittest.mock import MagicMock, patch

from aiohttp import ClientSession
from evohomeasync2 import EvohomeClient
import pytest

from homeassistant.components.evohome import (
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
    STORAGE_KEY,
    STORAGE_VER,
    dt_aware_to_naive,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .conftest import mock_get
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
    return dt_util.parse_datetime(dt_str), dt_str  # type: ignore[return-value]


ACCESS_TOKEN_EXP_DTM, ACCESS_TOKEN_EXP_STR = dt_pair(dt_util.now() + timedelta(hours=1))

USERNAME_DIFF: Final = f"not_{USERNAME}"
USERNAME_SAME: Final = USERNAME

TEST_CONFIG: Final = {
    CONF_USERNAME: USERNAME_SAME,
    CONF_PASSWORD: "password",
}

TEST_DATA: Final[dict[str, _TokenStoreT]] = {
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

TEST_DATA_NULL: Final[dict[str, _EmptyStoreT | None]] = {
    "store_is_absent": None,
    "store_was_reset": {},
}

DOMAIN_STORAGE_BASE: Final = {
    "version": STORAGE_VER,
    "minor_version": 1,
    "key": STORAGE_KEY,
}


@patch("evohomeasync2.broker.Broker.get", mock_get)
async def setup_evohome(hass: HomeAssistant, test_config: dict[str, str]) -> MagicMock:
    """Set up the evohome integration and return its client.

    The class is mocked here to check the client was instantiated with the correct args.
    """

    mock_client: EvohomeClient | None = None

    def capture_client(*args: Any, **kwargs: Any):
        nonlocal mock_client
        mock_client = EvohomeClient(*args, **kwargs)
        return mock_client

    with patch(
        "homeassistant.components.evohome.evo.EvohomeClient", side_effect=capture_client
    ) as mock_class:
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: test_config})
        await hass.async_block_till_done()

        mock_class.assert_called_once()
        assert mock_class.call_args.args[0] == test_config[CONF_USERNAME]
        assert mock_class.call_args.args[1] == test_config[CONF_PASSWORD]

        assert isinstance(mock_class.call_args.kwargs["session"], ClientSession)
        assert mock_client and mock_client.account_info is not None

        return mock_class


@pytest.mark.parametrize("idx", TEST_DATA_NULL)
async def test_auth_tokens_null(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    idx: str,
) -> None:
    """Test loading/saving authentication tokens when no cached tokens in the store."""

    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": TEST_DATA_NULL[idx]}

    mock_client_class = await setup_evohome(hass, TEST_CONFIG)

    # Confirm client was instantiated without tokens, as cache was empty...
    assert SZ_REFRESH_TOKEN not in mock_client_class.call_args.kwargs
    assert SZ_ACCESS_TOKEN not in mock_client_class.call_args.kwargs
    assert SZ_ACCESS_TOKEN_EXPIRES not in mock_client_class.call_args.kwarg

    # Confirm the expected tokens were cached to storage...
    data: _TokenStoreT = hass_storage[DOMAIN]["data"]

    assert data[SZ_USERNAME] == USERNAME_SAME
    assert data[SZ_REFRESH_TOKEN] == f"new_{REFRESH_TOKEN}"
    assert data[SZ_ACCESS_TOKEN] == f"new_{ACCESS_TOKEN}"
    assert dt_util.parse_datetime(data[SZ_ACCESS_TOKEN_EXPIRES]) > dt_util.now()  # type: ignore[operator]


@pytest.mark.parametrize("idx", TEST_DATA)
async def test_auth_tokens_same(
    hass: HomeAssistant, hass_storage: dict[str, Any], idx: str
) -> None:
    """Test loading/saving authentication tokens when matching username."""

    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": TEST_DATA[idx]}

    mock_client_class = await setup_evohome(hass, TEST_CONFIG)

    # Confirm client was instantiated with the cached tokens...
    assert mock_client_class.call_args.kwargs[SZ_REFRESH_TOKEN] == REFRESH_TOKEN
    assert mock_client_class.call_args.kwargs[SZ_ACCESS_TOKEN] == ACCESS_TOKEN
    assert mock_client_class.call_args.kwargs[
        SZ_ACCESS_TOKEN_EXPIRES
    ] == dt_aware_to_naive(ACCESS_TOKEN_EXP_DTM)

    # Confirm the expected tokens were cached to storage...
    data: _TokenStoreT = hass_storage[DOMAIN]["data"]

    assert data[SZ_USERNAME] == USERNAME_SAME
    assert data[SZ_REFRESH_TOKEN] == REFRESH_TOKEN
    assert data[SZ_ACCESS_TOKEN] == ACCESS_TOKEN
    assert dt_util.parse_datetime(data[SZ_ACCESS_TOKEN_EXPIRES]) == ACCESS_TOKEN_EXP_DTM


@pytest.mark.parametrize("idx", TEST_DATA)
async def test_auth_tokens_past(
    hass: HomeAssistant, hass_storage: dict[str, Any], idx: str
) -> None:
    """Test loading/saving authentication tokens with matching username, but expired."""

    dt_dtm, dt_str = dt_pair(dt_util.now() - timedelta(hours=1))

    # make this access token have expired in the past...
    test_data = TEST_DATA[idx].copy()
    test_data[SZ_ACCESS_TOKEN_EXPIRES] = dt_str

    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": test_data}

    mock_client_class = await setup_evohome(hass, TEST_CONFIG)

    # Confirm client was instantiated with the cached tokens...
    assert mock_client_class.call_args.kwargs[SZ_REFRESH_TOKEN] == REFRESH_TOKEN
    assert mock_client_class.call_args.kwargs[SZ_ACCESS_TOKEN] == ACCESS_TOKEN
    assert mock_client_class.call_args.kwargs[
        SZ_ACCESS_TOKEN_EXPIRES
    ] == dt_aware_to_naive(dt_dtm)

    # Confirm the expected tokens were cached to storage...
    data: _TokenStoreT = hass_storage[DOMAIN]["data"]

    assert data[SZ_USERNAME] == USERNAME_SAME
    assert data[SZ_REFRESH_TOKEN] == REFRESH_TOKEN
    assert data[SZ_ACCESS_TOKEN] == f"new_{ACCESS_TOKEN}"
    assert dt_util.parse_datetime(data[SZ_ACCESS_TOKEN_EXPIRES]) > dt_util.now()  # type: ignore[operator]


@pytest.mark.parametrize("idx", TEST_DATA)
async def test_auth_tokens_diff(
    hass: HomeAssistant, hass_storage: dict[str, Any], idx: str
) -> None:
    """Test loading/saving authentication tokens when unmatched username."""

    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": TEST_DATA[idx]}

    mock_client_class = await setup_evohome(
        hass, TEST_CONFIG | {CONF_USERNAME: USERNAME_DIFF}
    )

    # Confirm client was instantiated without tokens, as username was different...
    assert SZ_REFRESH_TOKEN not in mock_client_class.call_args.kwargs
    assert SZ_ACCESS_TOKEN not in mock_client_class.call_args.kwargs
    assert SZ_ACCESS_TOKEN_EXPIRES not in mock_client_class.call_args.kwarg

    # Confirm the expected tokens were cached to storage...
    data: _TokenStoreT = hass_storage[DOMAIN]["data"]

    assert data[SZ_USERNAME] == USERNAME_DIFF
    assert data[SZ_REFRESH_TOKEN] == f"new_{REFRESH_TOKEN}"
    assert data[SZ_ACCESS_TOKEN] == f"new_{ACCESS_TOKEN}"
    assert dt_util.parse_datetime(data[SZ_ACCESS_TOKEN_EXPIRES]) > dt_util.now()  # type: ignore[operator]
