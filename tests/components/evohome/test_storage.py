"""The tests for evohome storage load & save."""

from datetime import datetime
from typing import Any, Final
from unittest.mock import patch

import pytest

from homeassistant.components.evohome import (
    CONF_PASSWORD,
    CONF_USERNAME,
    DOMAIN,
    EvoBroker,
)
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component
import homeassistant.util.dt as dt_util

from .conftest import mock_get
from .const import (
    ACCESS_TOKEN,
    ACCESS_TOKEN_EXPIRES_DTM,
    ACCESS_TOKEN_EXPIRES_STR,
    DIFF_EMAIL_ADDRESS,
    REFRESH_TOKEN,
    SAME_EMAIL_ADDRESS,
    SESSION_ID,
)

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


@patch("evohomeasync2.broker.Broker.get", mock_get)
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

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: TEST_CONFIG})
    await hass.async_block_till_done()

    evo_broker: EvoBroker = hass.data[DOMAIN]["broker"]

    if not TEST_DATA[idx]:
        assert evo_broker.client.username == SAME_EMAIL_ADDRESS
        assert evo_broker.client.refresh_token == f"new_{REFRESH_TOKEN}"
        assert evo_broker.client.access_token == f"new_{ACCESS_TOKEN}"
        assert evo_broker.client.access_token_expires > datetime.now()

    else:
        assert evo_broker.client.username == SAME_EMAIL_ADDRESS
        assert evo_broker.client.refresh_token == REFRESH_TOKEN
        assert evo_broker.client.access_token == ACCESS_TOKEN
        assert evo_broker.client.access_token_expires == ACCESS_TOKEN_EXPIRES_DTM


@patch("evohomeasync2.broker.Broker.get", mock_get)
@pytest.mark.parametrize("idx", TEST_DATA)
async def test_load_auth_tokens_diff(
    hass: HomeAssistant, hass_storage: dict[str, Any], idx: str
) -> None:
    """Test restoring (invalid) authentication tokens when unmatched account."""

    hass_storage[DOMAIN] = {
        "version": 1,
        "minor_version": 1,
        "key": "evohome",
        "data": TEST_DATA[idx],
    }

    test_config = TEST_CONFIG.copy()
    test_config[CONF_USERNAME] = DIFF_EMAIL_ADDRESS

    assert await async_setup_component(hass, DOMAIN, {DOMAIN: test_config})
    await hass.async_block_till_done()

    evo_broker: EvoBroker = hass.data[DOMAIN]["broker"]

    assert evo_broker.client.username == DIFF_EMAIL_ADDRESS
    assert evo_broker.client.refresh_token == f"new_{REFRESH_TOKEN}"
    assert evo_broker.client.access_token == f"new_{ACCESS_TOKEN}"
    assert evo_broker.client.access_token_expires > datetime.now()


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
