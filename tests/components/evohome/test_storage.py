"""The tests for evohome storage load & save."""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Final
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

USERNAME_DIFF: Final = f"not_{USERNAME}"
USERNAME_SAME: Final = USERNAME

dt_util.set_default_time_zone(dt_util.UTC)

ACCESS_TOKEN_EXP_DTM: Final = dt_util.now() + timedelta(hours=1)  # is TZ-aware
ACCESS_TOKEN_EXP_STR: Final = ACCESS_TOKEN_EXP_DTM.isoformat()


TEST_CONFIG: Final = {
    CONF_USERNAME: USERNAME_SAME,
    CONF_PASSWORD: "password",
}

SZ_USERNAME: Final = "username"
SZ_REFRESH_TOKEN: Final = "refresh_token"
SZ_ACCESS_TOKEN: Final = "access_token"
SZ_ACCESS_TOKEN_EXPIRES: Final = "access_token_expires"
SZ_USER_DATA: Final = "user_data"


TEST_DATA: Final[dict[str, dict]] = {
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


TEST_DATA_NULL: Final[dict[str, Any]] = {
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
    """Return the EvohomeClient instantiated via async_setup_component()."""

    mock_client: EvohomeClient | None = None

    def capture_client(*args: Any, **kwargs: Any):
        nonlocal mock_client
        mock_client = EvohomeClient(*args, **kwargs)
        return mock_client

    with patch(
        "homeassistant.components.evohome.evo.EvohomeClient", side_effect=capture_client
    ) as mock_client_class:
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: test_config})
        await hass.async_block_till_done()

        mock_client_class.assert_called_once()
        assert mock_client_class.call_args.args[0] == test_config[CONF_USERNAME]
        assert mock_client_class.call_args.args[1] == test_config[CONF_PASSWORD]

        assert isinstance(mock_client_class.call_args.kwargs["session"], ClientSession)
        assert mock_client and mock_client.account_info is not None

        return mock_client_class


@pytest.mark.parametrize("idx", TEST_DATA_NULL)
async def test_auth_tokens_null(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    idx: str,
) -> None:
    """Test loading/saving authentication tokens when no cached tokens."""

    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": TEST_DATA_NULL[idx]}

    mock_client_class = await setup_evohome(hass, TEST_CONFIG)

    # Confirm client was instantiated without tokens, as cache was empty...
    assert SZ_REFRESH_TOKEN not in mock_client_class.call_args.kwargs
    assert SZ_ACCESS_TOKEN not in mock_client_class.call_args.kwargs
    assert SZ_ACCESS_TOKEN_EXPIRES not in mock_client_class.call_args.kwarg

    # Confirm the expected tokens were cached to storage...
    data = hass_storage[DOMAIN]["data"]

    assert data[SZ_USERNAME] == USERNAME_SAME
    assert data[SZ_REFRESH_TOKEN] == f"new_{REFRESH_TOKEN}"
    assert data[SZ_ACCESS_TOKEN] == f"new_{ACCESS_TOKEN}"
    assert data[SZ_ACCESS_TOKEN_EXPIRES] > dt_util.now().isoformat()


@pytest.mark.parametrize("idx", TEST_DATA)
async def test_auth_tokens_same(
    hass: HomeAssistant, hass_storage: dict[str, Any], idx: str
) -> None:
    """Test loading/saving authentication tokens when same username."""

    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": TEST_DATA[idx]}

    mock_client_class = await setup_evohome(hass, TEST_CONFIG)

    # Confirm client was instantiated with the cached tokens...
    assert mock_client_class.call_args.kwargs[SZ_REFRESH_TOKEN] == REFRESH_TOKEN
    assert mock_client_class.call_args.kwargs[SZ_ACCESS_TOKEN] == ACCESS_TOKEN
    assert mock_client_class.call_args.kwargs[
        SZ_ACCESS_TOKEN_EXPIRES
    ] == dt_aware_to_naive(ACCESS_TOKEN_EXP_DTM)

    # Confirm the expected tokens were cached to storage...
    data = hass_storage[DOMAIN]["data"]

    assert data[SZ_USERNAME] == USERNAME_SAME
    assert data[SZ_REFRESH_TOKEN] == REFRESH_TOKEN
    assert data[SZ_ACCESS_TOKEN] == f"new_{ACCESS_TOKEN}"
    assert data[SZ_ACCESS_TOKEN_EXPIRES] > dt_util.now().isoformat()


@pytest.mark.parametrize("idx", TEST_DATA)
async def test_auth_tokens_past(
    hass: HomeAssistant, hass_storage: dict[str, Any], idx: str
) -> None:
    """Test loading/saving authentication tokens that have expired."""

    # make this access token have expired in the past...
    test_data = TEST_DATA[idx].copy()
    test_data[SZ_ACCESS_TOKEN_EXPIRES] = (
        dt_util.now() - timedelta(hours=1)
    ).isoformat()

    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": test_data}

    mock_client_class = await setup_evohome(hass, TEST_CONFIG)

    # Confirm client was instantiated with the cached tokens...
    assert mock_client_class.call_args.kwargs[SZ_REFRESH_TOKEN] == REFRESH_TOKEN
    assert mock_client_class.call_args.kwargs[SZ_ACCESS_TOKEN] == ACCESS_TOKEN
    # assert mock_client_class.call_args.kwargs[SZ_ACCESS_TOKEN_EXPIRES] == dt_aware_to_naive(ACCESS_TOKEN_EXP_DTM)

    # Confirm the expected tokens were cached to storage...
    data = hass_storage[DOMAIN]["data"]

    assert data[SZ_USERNAME] == USERNAME_SAME
    assert data[SZ_REFRESH_TOKEN] == REFRESH_TOKEN
    assert data[SZ_ACCESS_TOKEN] == f"new_{ACCESS_TOKEN}"
    assert data[SZ_ACCESS_TOKEN_EXPIRES] > dt_util.now().isoformat()


@pytest.mark.parametrize("idx", TEST_DATA)
async def test_auth_tokens_diff(
    hass: HomeAssistant, hass_storage: dict[str, Any], idx: str
) -> None:
    """Test loading/saving authentication tokens when different username."""

    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": TEST_DATA[idx]}

    mock_client_class = await setup_evohome(
        hass, TEST_CONFIG | {CONF_USERNAME: USERNAME_DIFF}
    )

    # Confirm client was instantiated without tokens, as username was different...
    assert SZ_REFRESH_TOKEN not in mock_client_class.call_args.kwargs
    assert SZ_ACCESS_TOKEN not in mock_client_class.call_args.kwargs
    assert SZ_ACCESS_TOKEN_EXPIRES not in mock_client_class.call_args.kwarg

    # Confirm the expected tokens were cached to storage...
    data = hass_storage[DOMAIN]["data"]

    assert data[SZ_USERNAME] == USERNAME_DIFF
    assert data[SZ_REFRESH_TOKEN] == f"new_{REFRESH_TOKEN}"
    assert data[SZ_ACCESS_TOKEN] == f"new_{ACCESS_TOKEN}"
    assert data[SZ_ACCESS_TOKEN_EXPIRES] > dt_util.now().isoformat()
