"""The tests for evohome storage load & save."""

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
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .conftest import mock_get
from .const import (
    ACCESS_TOKEN,
    ACCESS_TOKEN_EXP_DTM,
    ACCESS_TOKEN_EXP_STR,
    ACCESS_TOKEN_EXP_TZ,
    REFRESH_TOKEN,
    SESSION_ID,
    USERNAME_DIFF,
    USERNAME_SAME,
)

TEST_CONFIG: Final = {
    CONF_USERNAME: USERNAME_SAME,
    CONF_PASSWORD: "password",
}


TEST_DATA: Final = {
    "sans_session_id": {
        CONF_USERNAME: USERNAME_SAME,
        "refresh_token": REFRESH_TOKEN,
        "access_token": ACCESS_TOKEN,
        "access_token_expires": ACCESS_TOKEN_EXP_STR,
    },
    "with_session_id": {
        CONF_USERNAME: USERNAME_SAME,
        "refresh_token": REFRESH_TOKEN,
        "access_token": ACCESS_TOKEN,
        "access_token_expires": ACCESS_TOKEN_EXP_STR,
        "user_data": {"sessionId": SESSION_ID},
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

    dt_util.set_default_time_zone(ACCESS_TOKEN_EXP_TZ)

    with patch(
        "homeassistant.components.evohome.evo.EvohomeClient", side_effect=capture_client
    ) as MockEvohomeClient:
        assert await async_setup_component(hass, DOMAIN, {DOMAIN: test_config})
        await hass.async_block_till_done()

        MockEvohomeClient.assert_called_once()
        assert MockEvohomeClient.call_args.args[0] == test_config[CONF_USERNAME]
        assert MockEvohomeClient.call_args.args[1] == test_config[CONF_PASSWORD]

        assert isinstance(MockEvohomeClient.call_args.kwargs["session"], ClientSession)
        assert mock_client and mock_client.account_info is not None

        return MockEvohomeClient


@pytest.mark.parametrize("idx", TEST_DATA_NULL)
async def test_auth_tokens_null(
    hass: HomeAssistant,
    hass_storage: dict[str, Any],
    idx: str,
) -> None:
    """Test loading/saving authentication tokens when no cached tokens."""

    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": TEST_DATA_NULL[idx]}

    MockClient = await setup_evohome(hass, TEST_CONFIG)

    # Confirm the client was instantiated with the correct kwargs...
    assert "refresh_token" not in MockClient.call_args.kwargs
    assert "access_token" not in MockClient.call_args.kwargs
    assert "access_token_expires" not in MockClient.call_args.kwarg

    # Confirm the expected tokens were cached to storage...
    assert hass_storage[DOMAIN]["data"][CONF_USERNAME] == USERNAME_SAME
    assert hass_storage[DOMAIN]["data"]["refresh_token"] == f"new_{REFRESH_TOKEN}"
    assert hass_storage[DOMAIN]["data"]["access_token"] == f"new_{ACCESS_TOKEN}"
    assert hass_storage[DOMAIN]["data"]["access_token_expires"] > str(dt_util.now())


@pytest.mark.parametrize("idx", TEST_DATA)
async def test_auth_tokens_same(
    hass: HomeAssistant, hass_storage: dict[str, Any], idx: str
) -> None:
    """Test loading/saving authentication tokens when same username."""

    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": TEST_DATA[idx]}

    MockClient = await setup_evohome(hass, TEST_CONFIG)

    # Confirm the client was instantiated with the correct kwargs...
    assert MockClient.call_args.kwargs["refresh_token"] == REFRESH_TOKEN
    assert MockClient.call_args.kwargs["access_token"] == ACCESS_TOKEN
    assert MockClient.call_args.kwargs["access_token_expires"] == ACCESS_TOKEN_EXP_DTM

    # Confirm the expected tokens were cached to storage...
    assert hass_storage[DOMAIN]["data"][CONF_USERNAME] == USERNAME_SAME
    assert hass_storage[DOMAIN]["data"]["refresh_token"] == REFRESH_TOKEN
    assert hass_storage[DOMAIN]["data"]["access_token"] == ACCESS_TOKEN
    assert hass_storage[DOMAIN]["data"]["access_token_expires"] == ACCESS_TOKEN_EXP_STR


@pytest.mark.parametrize("idx", TEST_DATA)
async def test_auth_tokens_diff(
    hass: HomeAssistant, hass_storage: dict[str, Any], idx: str
) -> None:
    """Test loading/saving authentication tokens when different username."""

    hass_storage[DOMAIN] = DOMAIN_STORAGE_BASE | {"data": TEST_DATA[idx]}

    MockClient = await setup_evohome(hass, TEST_CONFIG | {CONF_USERNAME: USERNAME_DIFF})

    # Confirm the client was instantiated with the correct kwargs...
    assert "refresh_token" not in MockClient.call_args.kwargs
    assert "access_token" not in MockClient.call_args.kwargs
    assert "access_token_expires" not in MockClient.call_args.kwarg

    # Confirm the expected tokens were cached to storage...
    assert hass_storage[DOMAIN]["data"][CONF_USERNAME] == USERNAME_DIFF
    assert hass_storage[DOMAIN]["data"]["refresh_token"] == f"new_{REFRESH_TOKEN}"
    assert hass_storage[DOMAIN]["data"]["access_token"] == f"new_{ACCESS_TOKEN}"
    assert hass_storage[DOMAIN]["data"]["access_token_expires"] > str(dt_util.now())
