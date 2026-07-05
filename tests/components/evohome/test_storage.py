"""The tests for evohome storage load & save."""

from datetime import datetime, timedelta
from typing import Any, Final, TypedDict

from evohomeasync.auth import SZ_SESSION_ID, SZ_SESSION_ID_EXPIRES
from evohomeasync2.auth import (
    SZ_ACCESS_TOKEN,
    SZ_ACCESS_TOKEN_EXPIRES,
    SZ_REFRESH_TOKEN,
)
import pytest

from homeassistant.components.evohome.const import DOMAIN, STORAGE_KEY, STORAGE_VER
from homeassistant.components.evohome.storage import _TokenStoreT
from homeassistant.const import CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from .conftest import setup_evohome
from .const import ACCESS_TOKEN, REFRESH_TOKEN, SESSION_ID, USERNAME


class _EmptyStoreT(TypedDict):
    pass


def dt_pair(dt_dtm: datetime) -> tuple[datetime, str]:
    """Return a datetime without milliseconds and its string representation."""
    dt_str = dt_dtm.isoformat(timespec="seconds")  # e.g. 2024-07-28T00:57:29+01:00
    return dt_util.parse_datetime(dt_str, raise_on_error=True), dt_str


ACCESS_TOKEN_EXP_DTM, ACCESS_TOKEN_EXP_STR = dt_pair(dt_util.now() + timedelta(hours=1))
_, SESSION_ID_EXP_STR = dt_pair(dt_util.now() + timedelta(minutes=15))

_TEST_STORAGE_BASE: Final[_TokenStoreT] = {
    CONF_USERNAME: USERNAME,
    SZ_REFRESH_TOKEN: REFRESH_TOKEN,
    SZ_ACCESS_TOKEN: ACCESS_TOKEN,
    SZ_ACCESS_TOKEN_EXPIRES: ACCESS_TOKEN_EXP_STR,
}

TEST_STORAGE_DATA: Final[dict[str, _TokenStoreT]] = {
    "sans_session_id": _TEST_STORAGE_BASE,
    "with_session_id": _TEST_STORAGE_BASE
    | {
        SZ_SESSION_ID: SESSION_ID,
        SZ_SESSION_ID_EXPIRES: SESSION_ID_EXP_STR,
    },  # pyright: ignore[reportAssignmentType]
}

TEST_STORAGE_NULL: Final[dict[str, _EmptyStoreT | None]] = {
    "store_is_absent": None,
    "store_was_reset": {},
}

DOMAIN_STORAGE_ROOT: Final = {
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
    """Test credentials manager when cache is empty."""

    hass_storage[DOMAIN] = DOMAIN_STORAGE_ROOT | {"data": TEST_STORAGE_NULL[idx]}

    async for _ in setup_evohome(hass, config, install=install):
        pass

    data: _TokenStoreT = hass_storage[DOMAIN]["data"]

    # Confirm the expected tokens were cached to storage...
    assert data[CONF_USERNAME] == USERNAME
    assert data[SZ_REFRESH_TOKEN] == f"new_{REFRESH_TOKEN}"
    assert data[SZ_ACCESS_TOKEN] == f"new_{ACCESS_TOKEN}"

    assert (expires := data.get(SZ_ACCESS_TOKEN_EXPIRES)) is not None
    assert dt_util.parse_datetime(expires, raise_on_error=True) > dt_util.now()


@pytest.mark.parametrize("install", ["minimal"])
@pytest.mark.parametrize("idx", TEST_STORAGE_DATA)
async def test_auth_tokens_same(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    config: dict[str, str],
    idx: str,
    install: str,
) -> None:
    """Test credentials manager when cache contains valid data for this user."""

    hass_storage[DOMAIN] = DOMAIN_STORAGE_ROOT | {"data": TEST_STORAGE_DATA[idx]}

    async for _ in setup_evohome(hass, config, install=install):
        pass

    data: _TokenStoreT = hass_storage[DOMAIN]["data"]

    # Confirm the expected tokens were cached to storage...
    assert data[CONF_USERNAME] == USERNAME
    assert data[SZ_REFRESH_TOKEN] == REFRESH_TOKEN
    assert data[SZ_ACCESS_TOKEN] == ACCESS_TOKEN

    assert (expires := data[SZ_ACCESS_TOKEN_EXPIRES]) is not None
    assert dt_util.parse_datetime(expires, raise_on_error=True) == ACCESS_TOKEN_EXP_DTM


@pytest.mark.parametrize("install", ["minimal"])
@pytest.mark.parametrize("idx", TEST_STORAGE_DATA)
async def test_auth_tokens_past(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    config: dict[str, str],
    idx: str,
    install: str,
) -> None:
    """Test credentials manager when cache contains expired data for this user."""

    # make this access token to have expired in the past...
    _, dt_str = dt_pair(dt_util.now() - timedelta(hours=1))

    test_data = TEST_STORAGE_DATA[idx].copy()  # shallow copy is OK here
    test_data[SZ_ACCESS_TOKEN_EXPIRES] = dt_str

    hass_storage[DOMAIN] = DOMAIN_STORAGE_ROOT | {"data": test_data}

    async for _ in setup_evohome(hass, config, install=install):
        pass

    data: _TokenStoreT = hass_storage[DOMAIN]["data"]

    # Confirm the expected tokens were cached to storage...
    assert data[CONF_USERNAME] == USERNAME
    assert data[SZ_REFRESH_TOKEN] == f"new_{REFRESH_TOKEN}"
    assert data[SZ_ACCESS_TOKEN] == f"new_{ACCESS_TOKEN}"

    assert (expires := data[SZ_ACCESS_TOKEN_EXPIRES]) is not None
    assert dt_util.parse_datetime(expires, raise_on_error=True) > dt_util.now()


@pytest.mark.parametrize("install", ["minimal"])
@pytest.mark.parametrize("idx", TEST_STORAGE_DATA)
async def test_auth_tokens_diff(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    config: dict[str, str],
    idx: str,
    install: str,
) -> None:
    """Test credentials manager when cache contains data for a different user."""

    # make this access token to be for a different user...
    hass_storage[DOMAIN] = DOMAIN_STORAGE_ROOT | {"data": TEST_STORAGE_DATA[idx]}
    config[CONF_USERNAME] = f"new_{USERNAME}"

    async for _ in setup_evohome(hass, config, install=install):
        pass

    data: _TokenStoreT = hass_storage[DOMAIN]["data"]

    # Confirm the expected tokens were cached to storage...
    assert data[CONF_USERNAME] == f"new_{USERNAME}"
    assert data[SZ_REFRESH_TOKEN] == f"new_{REFRESH_TOKEN}"
    assert data[SZ_ACCESS_TOKEN] == f"new_{ACCESS_TOKEN}"

    assert (expires := data[SZ_ACCESS_TOKEN_EXPIRES]) is not None
    assert dt_util.parse_datetime(expires, raise_on_error=True) > dt_util.now()
